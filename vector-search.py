import concurrent
import os
import logging
import statistics
from datetime import datetime
import resource

import redis
import numpy as np
from redis.cluster import ClusterNode
from redis.commands.search.field import VectorField, TextField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis.commands.search.query import Query

##
# How to run this:
#
# SINGLE NODE
# python3 -m venv venv && source venv/bin/activate && pip install "redis[hiredis]==5.0.*" && pip install numpy && python3 vector-search.py
#
# USING THE CLUSTER
# docker run --rm --env REDIS_TEST_USE_CLUSTER=1 --name vector-search-test --network redis_cluster_test_network_boy -v "$(pwd):/app" python:3.11 sh -c "pip install 'redis[hiredis]==5.0.*' && pip install numpy && python3 /app/vector-search.py"
# 
##

reset_index = False
concurrent_search = bool(os.getenv('REDIS_TEST_CONCURRENT_SEARCH', False))
use_cluster = bool(os.getenv('REDIS_TEST_USE_CLUSTER', False))

n_embeddings = int(os.getenv('REDIS_TEST_N_EMBEDDINGS', 1000000))
batch_size = 250000
n_search_vector_rounds = 200
n_parallel_requests = 50

format = '%(asctime)s %(message)s'
logging.basicConfig(level=logging.INFO, format=format)

if use_cluster is True:
    # Using a Redis Cluster.
    logging.info('Using a Redis Cluster')
    nodes = nodes = [
        ClusterNode('redis-stack-1', 6379),
        ClusterNode('redis-stack-2', 6379),
        ClusterNode('redis-stack-3', 6379),
        ClusterNode('redis-stack-4', 6379),
        ClusterNode('redis-stack-5', 6379),
        ClusterNode('redis-stack-6', 6379),
        ClusterNode('redis-stack-7', 6379),
        ClusterNode('redis-stack-8', 6379),
        ClusterNode('redis-stack-9', 6379),
        ClusterNode('redis-stack-10', 6379),
        ClusterNode('redis-stack-11', 6379),
        ClusterNode('redis-stack-12', 6379),
        ClusterNode('redis-stack-13', 6379),
        ClusterNode('redis-stack-14', 6379),
        ClusterNode('redis-stack-15', 6379),
        ClusterNode('redis-stack-16', 6379),
    ]
    redis_conn = redis.RedisCluster(startup_nodes=nodes)
else:
    # Working for single node
    logging.info('Using a single Redis instance')
    redis_conn = redis.Redis(host="localhost", port=6379)

INDEX_NAME = "identityembeddings"  # Vector Index Name
PREFIX = "model_embeddings:"  # RediSearch Key Prefix for the Index
embedding_size = 512

def get_index_definition():
    # schema
    schema = (
        TextField("id"),  # Tag Field Name
        VectorField("embedding",  # Vector Field Name
                    "HNSW", {  # Vector Index Type: FLAT or HNSW
                        "TYPE": "FLOAT32",  # FLOAT32 or FLOAT64
                        "DIM": embedding_size,  # Number of Vector Dimensions
                        "DISTANCE_METRIC": "COSINE",  # Vector Search Distance Metric
                    }
                    ),
    )

    # index Definition
    definition = IndexDefinition(prefix=[PREFIX], index_type=IndexType.HASH)

    return schema, definition

def create_index(r):
    try:
        # check to see if index exists
        r.ft(INDEX_NAME).info()
        if reset_index is False:
            # Return false if it already exists and the script it set up to not reset it.
            return False

        r.ft(INDEX_NAME).dropindex(delete_documents=True)
        logging.info(f'Previous index dropped')

        # create Index
        schema, definition = get_index_definition()
        res = r.ft(INDEX_NAME).create_index(fields=schema, definition=definition)
        logging.info(f'Index created')

    except:

        # create Index
        schema, definition = get_index_definition()
        r.ft(INDEX_NAME).create_index(fields=schema, definition=definition)
        logging.info(f'Index created')

    # Return true when the index is created so that we can populate it.
    return True

def populate_index(r, n_embeddings: int):

    logging.info(f'Populating index with {n_embeddings} embeddings')

    if n_embeddings % batch_size != 0:
        raise Exception('n_embeddings % batch_size != 0!')

    identity_id = 1
    for i in range(n_embeddings // batch_size):

        for j in range(batch_size):

            # Single transaction
            # pipe = r.pipeline()

            key = f'{PREFIX}{identity_id}'
            obj = {
                'id': identity_id,
                'embedding': rand_embedding()
            }

            r.hset(key, mapping=obj)
            identity_id = identity_id + 1

        # res = pipe.execute()
        logging.info(f'Batch {i} completed')

    logging.info(f'All {n_embeddings} identities added')

def search_index(r):

    embedding = rand_embedding()

    start = datetime.now()

    query_stmt = Query("*=>[KNN 1 @embedding $input_embedding AS score]")
    query_params = {
        "input_embedding": embedding
    }

    query = (
        query_stmt
        .sort_by("score")
        .return_fields("id", "score")
        .paging(0, 1)
        .dialect(4)
    )

    result = r.ft(INDEX_NAME).search(query, query_params).docs

    end = datetime.now() - start
    duration = end.total_seconds()
    # logging.info(f'Duration: {duration}')

    # We ignore the result, likely to be commented out, just for spike purposes.
    # logging.info(result)

    return duration

def rand_embedding():
    return np.random.rand(embedding_size).astype(np.float32).tobytes()

if create_index(redis_conn) is True:
    populate_index(redis_conn, n_embeddings)


if concurrent_search is False:
    mode = 'sequentially'
else:
    mode = f'concurrently ({n_parallel_requests} requests in parallel)'

logging.info(f'Search random vectors {mode} to check the time it takes')

start = datetime.now()
if concurrent_search:
    with concurrent.futures.ThreadPoolExecutor(max_workers=n_parallel_requests) as executor:
        futures = [executor.submit(search_index, redis_conn) for _ in range(n_search_vector_rounds)]
        list_of_search_times = [future.result() for future in concurrent.futures.as_completed(futures)]
else:
    list_of_search_times = []
    for i in range(n_search_vector_rounds):
        result = search_index(redis_conn)
        list_of_search_times.append(result)
duration = datetime.now() - start

logging.info(f'Average time to search 1 vector (misleading results on concurrent): {statistics.mean(list_of_search_times)}s\tStandard Deviation: {statistics.stdev(list_of_search_times)}s')
logging.info(f'Total search time for {n_search_vector_rounds} search queries of 1 vector: {duration.total_seconds()}s')
