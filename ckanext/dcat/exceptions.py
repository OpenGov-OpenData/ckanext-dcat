# -*- coding: utf-8 -*-
import json


class RDFParserException(Exception):
    pass


class RDFProfileException(Exception):
    pass


class JSONDecodeErrorContext(json.JSONDecodeError):
    def __init__(self, msg, doc, pos):
        super().__init__(msg, doc, pos)
        # Build context using the provided document
        content_lines = doc.splitlines()
        error_index = self.lineno - 1
        error_lines = []

        # Append the previous line if available
        if error_index > 0:
            error_lines.append(f"{error_index}: {content_lines[error_index - 1]}")

        # Append the error line
        error_lines.append(f"{error_index + 1}: {content_lines[error_index]}")

        # Append the next line if available
        if error_index + 1 < len(content_lines):
            error_lines.append(f"{error_index + 2}: {content_lines[error_index + 1]}")

        self.context_msg = "\n".join(error_lines)

    def __str__(self):
        base_str = super().__str__()
        return f"{base_str}\nJSONDecodeErrorContext\n{self.context_msg}"
