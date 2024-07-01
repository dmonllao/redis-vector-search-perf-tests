#!/bin/bash

replica_ip=$(ifconfig eth1 | grep 'inet ' | awk '{print $2}')
echo "${replica_ip}" > ./info-replica-ip
echo "IP: ${replica_ip}"

# We need to manually add the loaded libraries if we overwrite the redis-server command.
# Save a backup every N seconds if there are M changes in the dataset
# We enable the appendonly copy of the data with appendfsync to always. This set of redis nodes will not be used for caching
# We should be getting new identity embedding keys only every few seconds / minutes.
# More info: https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/
redis-server --loadmodule "/opt/redis-stack/lib/redisearch-coord-custom-build.so" --loadmodule "/opt/redis-stack/lib/rejson.so" \
  --bind "* -::*" \
  --port 6379 \
  --cluster-enabled "yes" \
  --cluster-port 16379 \
  --cluster-announce-ip "${replica_ip}" \
  --cluster-announce-bus-port 16379 \
  --cluster-announce-port 6379 \
  --protected-mode "no"
#  --appendonly yes
#  --appendfsync always
#  --save "3600 100"