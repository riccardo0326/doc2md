class Doc2MdError(Exception):
    """Base class for expected doc2md failures."""


class ConfigError(Doc2MdError):
    """The requested operation or configuration is invalid."""


class SourceError(Doc2MdError):
    """The input document cannot be opened or read."""


class HardExtractionError(Doc2MdError):
    """The hard-path document extractor failed."""


class ConversionFailed(Doc2MdError):
    """Strict conversion found one or more failed pages."""
