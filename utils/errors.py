"""Application-specific error types and user-facing messages."""


class CRISPRError(Exception):
    """Base exception for IndelQuant."""

    LEVEL_WARNING = 'warning'
    LEVEL_ERROR = 'error'
    LEVEL_CRITICAL = 'critical'

    def __init__(self, message, suggestion='', level=LEVEL_ERROR):
        super().__init__(message)
        self._message = message
        self._suggestion = suggestion
        self._level = level

    def user_message(self):
        msg = self._message
        if self._suggestion:
            msg += f'\n\nSuggestion: {self._suggestion}'
        return msg

    @property
    def suggestion(self):
        return self._suggestion

    @property
    def level(self):
        return self._level

    def __str__(self):
        return self._message


class FileError(CRISPRError):
    """File-related error."""

    def __init__(self, path, reason='', suggestion=''):
        if not suggestion:
            suggestion = self._auto_suggest(path, reason)
        message = f'File error: {path}'
        if reason:
            message += f' - {reason}'
        super().__init__(message, suggestion)

    @staticmethod
    def _auto_suggest(path, reason):
        reason_lower = reason.lower() if reason else ''
        if 'not found' in reason_lower or 'does not exist' in reason_lower:
            return f'Check that the file path is correct: {path}\nUse Browse to select the file again.'
        if 'permission' in reason_lower:
            return 'The file may be open in another program or you may not have access permission. Close the file and try again.'
        if 'encoding' in reason_lower:
            return 'The file encoding may not be UTF-8. Convert it to UTF-8 and try again.'
        if 'empty' in reason_lower:
            return 'The file is empty. Check that it was generated correctly.'
        return 'Check that the file path and content are correct.'


class ParamError(CRISPRError):
    """Parameter-related error."""

    def __init__(self, param_name, reason='', suggestion=''):
        if not suggestion:
            suggestion = self._auto_suggest(param_name, reason)
        message = f'Parameter error: {param_name}'
        if reason:
            message += f' - {reason}'
        super().__init__(message, suggestion)

    @staticmethod
    def _auto_suggest(param_name, reason):
        param_lower = param_name.lower()
        if 'amplicon' in param_lower:
            return 'Enter a valid amplicon reference sequence containing only ATCG bases.'
        if 'sgrna' in param_lower or 'guide' in param_lower:
            return 'Enter a valid sgRNA sequence without PAM, usually 20 bp.'
        if 'barcode' in param_lower:
            return 'Select a barcode table file in the format: Sample name<TAB>barcode sequence.'
        if 'output' in param_lower:
            return 'Select a valid output directory path.'
        if 'thread' in param_lower or 'process' in param_lower:
            return 'Enter a valid positive integer. A value no higher than the CPU core count is recommended.'
        return 'Check that the parameter value is correct.'


class ToolError(CRISPRError):
    """External tool execution error."""

    def __init__(self, tool_name, reason='', returncode=None, stderr='', suggestion=''):
        if not suggestion:
            suggestion = self._auto_suggest(tool_name, reason, returncode)
        message = f'{tool_name} failed'
        if returncode is not None:
            message += f' (return code: {returncode})'
        if reason:
            message += f': {reason}'
        if stderr:
            stderr_text = stderr.strip()
            if stderr_text:
                message += f'\n{stderr_text}'
        super().__init__(message, suggestion)

    @staticmethod
    def _auto_suggest(tool_name, reason, returncode):
        name_lower = tool_name.lower()
        reason_lower = (reason or '').lower()
        if 'adapterremoval' in name_lower:
            if returncode == 1:
                return 'Check the input file format and AdapterRemoval parameters.'
            if returncode and returncode < 0:
                return 'The process was terminated by the system, possibly because of insufficient memory. Try fewer threads or a smaller dataset.'
            return 'Check that AdapterRemoval is installed correctly. Use Check Environment on the Environment page.'
        if 'crispresso' in name_lower:
            if returncode == 1:
                return 'Check the amplicon/sgRNA sequences and CRISPResso2 parameters. Common issues include sequence format errors and output directory permissions.'
            if returncode and returncode < 0:
                return 'The process was terminated by the system, possibly because of insufficient memory. Try fewer processes or a smaller dataset.'
            if 'not found' in reason_lower:
                return 'CRISPResso2 was not found. Check the Conda environment on the Environment page or install it with: pip install CRISPResso2'
            return 'Check that CRISPResso2 is installed correctly. Use Check Environment on the Environment page.'
        return 'Check that the tool is installed and that the parameters are correct.'


class EnvError(CRISPRError):
    """Runtime environment error."""

    def __init__(self, component, reason='', suggestion=''):
        if not suggestion:
            suggestion = self._auto_suggest(component, reason)
        message = f'Environment error: {component}'
        if reason:
            message += f' - {reason}'
        super().__init__(message, suggestion, level=self.LEVEL_CRITICAL)

    @staticmethod
    def _auto_suggest(component, reason):
        comp_lower = component.lower()
        if 'conda' in comp_lower:
            return 'Install Miniconda or Anaconda: https://docs.conda.io/en/latest/miniconda.html'
        if 'environment' in comp_lower:
            return 'Create the crispranalysis environment from the Environment page.'
        if 'python' in comp_lower:
            return 'Install Python 3.10 in the Conda environment.'
        return 'Check the environment configuration on the Environment page.'


def format_error_for_log(error):
    """Format an exception for detailed logging."""
    if isinstance(error, CRISPRError):
        level_tag = f'[{error.level.upper()}]'
        msg = f'{level_tag} {error}'
        if error.suggestion:
            msg += f' | Suggestion: {error.suggestion}'
        return msg
    return f'[ERROR] {type(error).__name__}: {error}'


def get_user_friendly_message(error):
    """Convert an exception to a user-facing message."""
    if isinstance(error, CRISPRError):
        return error.user_message()
    if isinstance(error, FileNotFoundError):
        return f'File not found: {error}\n\nSuggestion: Check that the file path is correct.'
    if isinstance(error, PermissionError):
        return f'Permission denied: {error}\n\nSuggestion: Check file or directory access permissions.'
    if isinstance(error, TimeoutError):
        return f'Operation timed out: {error}\n\nSuggestion: The dataset may be too large. Try fewer samples or increase the timeout.'
    if isinstance(error, InterruptedError):
        return 'The operation was interrupted by the user.'
    if isinstance(error, MemoryError):
        return 'Insufficient memory.\n\nSuggestion: Try fewer threads/processes or a smaller dataset.'
    return f'An error occurred: {type(error).__name__}: {error}'
