# -*- coding: utf-8 -*-
"""JingniFlow 统一异常体系。"""


class JingniError(Exception):
    """所有 JingniFlow 异常的基类。"""

    code = "JINGNI_ERROR"
    platform = None

    def __init__(self, message, code=None, platform=None, details=None):
        Exception.__init__(self, message)
        self.message = message
        if code is not None:
            self.code = code
        if platform is not None:
            self.platform = platform
        self.details = details or {}

    def __str__(self):
        if self.platform:
            return "[{0}:{1}] {2}".format(self.code, self.platform, self.message)
        return "[{0}] {1}".format(self.code, self.message)


class ValidationError(JingniError):
    code = "JINGNI_VALIDATION"


class UnsupportedFeature(JingniError):
    code = "JINGNI_UNSUPPORTED"

    def __init__(self, platform, feature, message=None):
        if message is None:
            message = "platform {0} does not support feature {1}".format(
                platform, feature
            )
        JingniError.__init__(
            self,
            message,
            code=self.code,
            platform=platform,
            details={"feature": feature},
        )
        self.feature = feature


class PlatformApiMissing(JingniError):
    code = "JINGNI_PLATFORM_API_MISSING"


class DataError(JingniError):
    code = "JINGNI_DATA_ERROR"


class OrderError(JingniError):
    code = "JINGNI_ORDER_ERROR"
