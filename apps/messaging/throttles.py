from rest_framework.throttling import UserRateThrottle


class TradeMessageRateThrottle(UserRateThrottle):
    scope = "trade_message"
