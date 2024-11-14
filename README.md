Tool to compare the performance of redis search

### Start the redis cluster and the single node instance

```
docker compose -f docker-compose.redis-cluster-swarm.yml build
docker swarm init
docker stack deploy -c docker-compose.redis-cluster-swarm.yml redis-cluster
docker compose -f docker-compose.redis-single-instance.yml up -d
```

### Index random embeddings + search

```
# Run search on one single redis instance (single CPU usage)
python3 -m venv venv && source venv/bin/activate && pip install "redis[hiredis]==5.0.*" && pip install numpy && python3 vector-search.py && docker exec redis-vector-search-perf-tests-redis_single_instance-1 redis-cli info && docker logs redis-vector-search-perf-tests-redis_single_instance-1
# Collect the stats for comparison
docker exec redis-vector-search-perf-tests-redis_single_instance-1 redis-cli info && docker logs redis-vector-search-perf-tests-redis_single_instance-1

# Run search on a redis cluster of 16 nodes (one per CPU)
docker run --rm --env REDIS_TEST_USE_CLUSTER=1 --name vector-search-test --network redis_cluster_test_network_boy -v "./:/app" python:3.11 sh -c "pip install 'redis[hiredis]==5.0.*' && pip install numpy && python3 /app/vector-search.py"
# Collect the stats for comparison
CONTAINER_ID=$(docker ps --filter "name=redis-cluster_redis-stack-1" --format "{{.ID}}" | head -n 1) && docker exec $CONTAINER_ID redis-cli info && docker logs $CONTAINER_ID

```
