from typing import TypedDict


class EmailConfigSchema(TypedDict, total=False):
    """TypedDict defining all possible email configuration options."""

    EMAIL_BATCH_SIZE: int
    EMAIL_RETRY_ATTEMPTS: int
    EMAIL_RETRY_DELAY: int
    EMAIL_MAX_RECIPIENTS: int
    EMAIL_THREAD_POOL_SIZE: int
    PLATFORM_NAME: str
    PLATFORM_ADDRESS: str
    PLATFORM_CONTACT_EMAIL: str
    UNSUBSCRIBE_LINK: str
