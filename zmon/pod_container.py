def check():
    result = {}

    namespaces = ['default']

    def get_heapster_metric(namespace, pod_name, metric_name):
        heapster_base_url = 'http://heapster.kube-system.svc.cluster.local'
        res = http(
            '{url}/api/v1/model/namespaces/{namespace}/pods/{pod}/metrics/{metric}'.format(url=heapster_base_url,
                                                                                           namespace=namespace,
                                                                                           pod=pod_name,
                                                                                           metric=metric_name)).json()
        latest_timestamp = res['latestTimestamp']
        metrics = res['metrics']
        for m in metrics:
            if m['timestamp'] == latest_timestamp:
                return m['value']

    def prometheus_selector(c_name, p_name, namespace):
        return """{{container_name="{0}", pod_name="{1}", namespace="{2}"}}""".format(c_name, p_name, namespace)

    def get_prometheus_metric(query):
        prometheus_url = 'http://prometheus.kube-system.svc.cluster.local/api/v1/query'
        res = http(prometheus_url, params={'query': query}).json()
        if res.get('status') == 'success':
            _, value = res['data']['result']
            return float(value)
        else:
            return float('nan')

    def usage_ratio(usage, max):
        if max == 0:
            return 0
        else:
            return float(usage) / float(max)

    def handle_cpu_limit(value):
        default_limit = 3000  # default value assigned if you don't specify limit
        return default_limit if value is None or str(value) == 'nan' or str(value) == '' or value == 0 else value

    def collect_pod_metrics(namespace, pod_name):
        cpu_request = get_heapster_metric(namespace, pod_name, 'cpu/request')
        cpu_limit = handle_cpu_limit(get_heapster_metric(namespace, pod_name, 'cpu/limit'))
        cpu_usage = get_heapster_metric(namespace, pod_name, 'cpu/usage_rate')

        memory_request = get_heapster_metric(namespace, pod_name, 'memory/request')
        memory_limit = get_heapster_metric(namespace, pod_name, 'memory/limit')
        memory_usage = get_heapster_metric(namespace, pod_name, 'memory/usage')

        return {
            "cpu/usage": cpu_usage,
            "cpu/request": cpu_request,
            "cpu/limit": cpu_limit,
            "cpu/usage_ratio": usage_ratio(cpu_usage, cpu_limit),
            "cpu/usage_request_ratio": usage_ratio(cpu_usage, cpu_request),
            "cpu/limit_request_ratio": usage_ratio(cpu_limit, cpu_request),
            "memory/usage": memory_usage,
            "memory/request": memory_request,
            "memory/limit": memory_limit,
            "memory/usage_ratio": usage_ratio(memory_usage, memory_limit),
            "memory/usage_request_ratio": usage_ratio(memory_usage, memory_request),
            "memory/limit_request_ratio": usage_ratio(memory_limit, memory_request)
        }

    def collect_container_metrics(selector):
        # CPU
        cpu_request = get_prometheus_metric(
            """1000 * scalar(kube_pod_container_resource_requests_cpu_cores{selector})""".format(selector=selector))
        cpu_limit = handle_cpu_limit(get_prometheus_metric(
            """1000 * scalar(kube_pod_container_resource_limits_cpu_cores{selector})""".format(selector=selector)))
        cpu_usage = get_prometheus_metric(
            """1000 * scalar(sum(rate(container_cpu_usage_seconds_total{selector}[1m])))""".format(selector=selector))

        # Memory
        memory_request = get_prometheus_metric(
            """scalar(kube_pod_container_resource_requests_memory_bytes{selector})""".format(selector=selector))
        memory_limit = get_prometheus_metric(
            """scalar(kube_pod_container_resource_limits_memory_bytes{selector})""".format(selector=selector))
        memory_usage = get_prometheus_metric(
            """scalar(container_memory_working_set_bytes{selector})""".format(selector=selector))

        return {
            "cpu/usage": cpu_usage,
            "cpu/request": cpu_request,
            "cpu/limit": cpu_limit,
            "cpu/usage_ratio": usage_ratio(cpu_usage, cpu_limit),
            "cpu/usage_request_ratio": usage_ratio(cpu_usage, cpu_request),
            "cpu/limit_request_ratio": usage_ratio(cpu_limit, cpu_request),
            "memory/usage": memory_usage,
            "memory/request": memory_request,
            "memory/limit": memory_limit,
            "memory/usage_ratio": usage_ratio(memory_usage, memory_limit),
            "memory/usage_request_ratio": usage_ratio(memory_usage, memory_request),
            "memory/limit_request_ratio": usage_ratio(memory_limit, memory_request)
        }

    for namespace in namespaces:
        pods = kubernetes(namespace=namespace).pods()

        for pod in pods:
            pod_name = pod['metadata']['name']
            result[pod_name] = {'count': 1, 'c': {}}

            pod_metrics = collect_pod_metrics(namespace, pod_name)

            for metric in pod_metrics:
                result[pod_name][metric] = pod_metrics[metric]

            for status in pod['status'].get('initContainerStatuses', []):
                c_name = status['name']
                if c_name not in result[pod_name]['c']:
                    result[pod_name]['c'][c_name] = {'c_count': 1}
                result[pod_name]['c'][c_name]['c_restart_count'] = status['restartCount']

            for status in pod['status'].get('containerStatuses', []):
                c_name = status['name']
                if c_name not in result[pod_name]['c']:
                    result[pod_name]['c'][c_name] = {'c_count': 1}
                result[pod_name]['c'][c_name]['c_restart_count'] = status['restartCount']

                container_metrics = collect_container_metrics(prometheus_selector(c_name, pod_name, namespace))
                for m in container_metrics:
                    result[pod_name]['c'][c_name]['c_' + m] = container_metrics[m]

    return result
