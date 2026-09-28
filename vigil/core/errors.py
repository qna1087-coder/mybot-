"""Domain errors. Handlers translate these into calm, specific microcopy."""


class VigilError(Exception):
    code = "error"


class NotAuthorized(VigilError):
    code = "not_authorized"


class ChannelNotActive(VigilError):
    code = "channel_not_active"


class AdminNotManaged(VigilError):
    """The administrator was promoted outside Vigil; Telegram will not let the bot demote them."""

    code = "admin_not_managed"


class BotRightsMissing(VigilError):
    code = "bot_rights_missing"

    def __init__(self, missing: list[str]):
        super().__init__(", ".join(missing))
        self.missing = missing


class TelegramFailure(VigilError):
    code = "telegram_failure"


class ModerationUnavailable(VigilError):
    code = "moderation_unavailable"


class InvalidInput(VigilError):
    code = "invalid_input"
