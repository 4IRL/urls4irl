class HEALTH_STRS:
    COMPONENTS = "components"
    POSTGRES = "postgres"
    SESSION_REDIS = "session_redis"
    METRICS_REDIS = "metrics_redis"
    UNAUTHORIZED = "Unauthorized"
    UNHEALTHY_PREFIX = "Unhealthy components: "
    # Fixed order used for the component dict and the 503 message.
    COMPONENT_ORDER = (POSTGRES, SESSION_REDIS, METRICS_REDIS)
