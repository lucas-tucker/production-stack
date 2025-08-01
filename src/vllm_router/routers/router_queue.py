# Copyright 2024-2025 The vLLM Production Stack Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from abc import ABC
import asyncio
from collections import deque
from fastapi import Request
from heapq import heappush, heapify, heappop
import threading
import time
from typing import Dict, List
from vllm_router.service_discovery import get_service_discovery
from vllm_router.routers.routing_logic import RoutingInterface
from vllm_router.log import init_logger
from vllm_router.service_discovery import EndpointInfo
from vllm_router.stats.engine_stats import EngineStats
from vllm_router.stats.request_stats import RequestStats
from vllm_router.utils import SingletonABCMeta

class RouterPriorityQueue(RoutingInterface):
    """
    qps-based queue router, where requests are prioritized based on time in this
    initial implementation
    """
    def __init__(self, qps_threshold=10):
        self._queue = deque()
        self._qps_threshold = qps_threshold

    async def enqueue_request(self, request_json):
        self._queue.append(request_json)

    async def route_request(
        self,
        endpoints: List[EndpointInfo],
        engine_stats: Dict[str, EngineStats],
        request_stats: Dict[str, RequestStats],
        request: Request,
        request_json: Dict,
    ):
        self.enqueue_request(request_json)
        # spin...
        while self._queue[0] != request_json:
            time.sleep(0.1)
        # route and then pop
        lowest_qps = float("inf")
        while lowest_qps > self._qps_threshold:
            time.sleep(0.1)
            request_stats = request.app.state.request_stats_monitor.get_request_stats(
                time.time()
            )
            url = self._qps_routing(
                endpoints,
                request_stats
            )
            if url not in request_stats:
                lowest_qps = 0
            else:
                lowest_qps = request_stats[url]
        # lowest_qps is below qps threshold
        url = self._qps_routing(
            endpoints,
            request_stats
        )
        self._queue.popleft()
        return url
    
    # async def dequeue_request(self):
    #     next_req = heappop(self._heap)[-1]
    #     self.route_request(
    #         endpoints,
    #         engine_stats,
    #         request_stats,
    #         next_req,
    #         False # This is the to_queue variable
    #     )
    
    # async def periodic_qps_check(self):
    #     """
    #     Daemon that periodically checks the QPS of relevant endpoints and performs
    #     qps based routing if applicable 
    #     """
    #     # request_json = 
    #     # requested_model = request_json.get("model", None)
    #     # aliases = getattr(service_discovery, "aliases", None)
    #     # if aliases and requested_model in aliases.keys():
    #     #     requested_model = aliases[requested_model]
    #     # service_discovery = get_service_discovery()
    #     # endpoints = service_discovery.get_endpoint_info()
    #     # endpoints = list(
    #     #     filter(
    #     #         lambda x: requested_model in x.model_names and not x.sleep,
    #     #         endpoints,
    #     #     )
    #     # )
    #     while self._heap:
    #         time.sleep(0.01)

            

    # def start_qps_monitoring(self):
    #     """
    #     Start the kv manager
    #     """
    #     self.loop = asyncio.new_event_loop()
    #     self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
    #     self.thread.start()
    #     asyncio.run_coroutine_threadsafe(self.periodic_qps_check(), self.loop)

    # def _get_last_prompt(self, request_json):
    #     if "messages" in request_json:
    #         # Get the last message from the messages array
    #         messages = request_json["messages"]
    #         if messages:
    #             last_message = messages[-1]
    #             prompt = last_message.get("content", "")
    #             if isinstance(prompt, list):
    #                 # Handle multimodal messages
    #                 prompt = " ".join(
    #                     part.get("text", "")
    #                     for part in prompt
    #                     if part.get("type") == "text"
    #                 )
    #             return prompt
    #         else:
    #             return ""
    #     else:
    #         # Regular completions
    #         return request_json["prompt"],

# ```bash
# vllm-router --port 8800 \
#     --service-discovery static \
#     --static-backends "http://localhost:9001,http://localhost:9002" \
#     --static-models "meta-llama/Llama-3.1-8B-Instruct,meta-llama/Llama-3.1-8B-Instruct" \
#     --static-aliases "gpt4:meta-llama/Llama-3.1-8B-Instruct" \
#     --static-model-types "chat,chat" \
#     --static-backend-health-checks \
#     --engine-stats-interval 10 \
#     --log-stats \
#     --routing-logic roundrobin
# ```