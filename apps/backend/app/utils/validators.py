"""Input validation and sanitization utilities."""

import re
from typing import Optional
from ..utils.exceptions import ValidationError


def sanitize_string(
    input_string: str,
    max_length: int = 255,
    allow_html: bool = False
) -> str:
    """Sanitize string input to prevent injection attacks"""
    if not input_string:
        return ""

    # Ensure string
    if not isinstance(input_string, str):
        try:
            input_string = str(input_string)
        except Exception:
            raise ValidationError("Invalid string input")

    # Trim whitespace
    sanitized = input_string.strip()

    # Check length
    if len(sanitized) > max_length:
        raise ValidationError(
            f"Input exceeds maximum length of {max_length} characters"
        )

    # Remove HTML if not allowed
    if not allow_html:
        sanitized = re.sub(r'<[^>]*>', '', sanitized)

    # Escape special characters to prevent injection
    # Using proper escaping sequences
    sanitized = sanitized.replace('\\', '\\\\')  # Backslash first
    sanitized = sanitized.replace('"', '\\"')     # Double quote
    sanitized = sanitized.replace("'", "\\'")     # Single quote
    sanitized = sanitized.replace("`", "\\`")     # Backtick
    sanitized = sanitized.replace("$", "\\$")     # Dollar sign
    sanitized = sanitized.replace("%", "\\%")     # Percent

    return sanitized


def sanitize_phone(phone_number: str) -> str:
    """Sanitize and format phone number"""
    if not phone_number:
        raise ValidationError("Phone number is required")

    # Remove all non-digit characters
    digits = re.sub(r'\D', '', phone_number)

    # Validate length (min 10 digits)
    if len(digits) < 10:
        raise ValidationError("Phone number must have at least 10 digits")

    # Format with country code if missing
    if not digits.startswith("1"):
        digits = f"+{digits}"
    else:
        digits = f"+{digits}"

    return digits


def validate_email(email: str) -> str:
    """Validate email format"""
    if not email:
        raise ValidationError("Email is required")

    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        raise ValidationError("Invalid email format")

    return email.lower().strip()


def validate_url(url: str) -> str:
    """Validate URL format"""
    if not url:
        raise ValidationError("URL is required")

    pattern = r'https?://(www\.)?[-a-zA-Z0-9@:%._+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_+.~#?&//=]*)'
    if not re.match(pattern, url):
        raise ValidationError("Invalid URL format")

    return url.strip()


def validate_campaign_name(name: str) -> str:
    """Validate campaign name"""
    sanitized = sanitize_string(name, max_length=100)

    if len(sanitized) < 3:
        raise ValidationError("Campaign name must be at least 3 characters")

    # Check for disallowed characters
    if re.search(r'[<>&"\'\;]', sanitized):
        raise ValidationError("Campaign name contains invalid characters")

    return sanitized


def validate_status(status: str, valid_statuses: list) -> str:
    """Validate status against allowed values"""
    status = status.lower().strip()

    if status not in valid_statuses:
        raise ValidationError(
            f"Invalid status '{status}'. Must be one of: {', '.join(valid_statuses)}"
        )

    return status


def validate_uuid(uuid_string: str) -> str:
    """Validate UUID format"""
    pattern = r'^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$'
    if not re.match(pattern, uuid_string, re.IGNORECASE):
        raise ValidationError("Invalid UUID format")

    # Normalize format (remove hyphens and re-add in correct positions)
    uuid_hex = uuid_string.replace('-', '').lower()
    return f"{uuid_hex[:8]}-{uuid_hex[8:12]}-{uuid_hex[12:16]}-{uuid_hex[16:20]}-{uuid_hex[20:]}"


def validate_csv_file(file_content: bytes) -> str:
    """Validate and process CSV file content"""
    try:
        import csv
        import io

        # Decode and check for BOM
        content = file_content.decode('utf-8-sig')

        # Parse CSV
        reader = csv.DictReader(io.StringIO(content))

        # Validate headers
        required_fields = {'phone_number'}
        actual_fields = set(reader.fieldnames or [])

        if not required_fields.issubset(actual_fields):
            raise ValidationError(
                f"CSV file must contain field: phone_number. Found: {', '.join(actual_fields)}"
            )

        return content

    except UnicodeDecodeError:
        raise ValidationError("CSV file must be UTF-8 encoded")
    except csv.Error as e:
        raise ValidationError(f"Invalid CSV format: {str(e)}")


def sanitize_metadata(metadata: dict) -> dict:
    """Sanitize metadata dictionary"""
    if not isinstance(metadata, dict):
        raise ValidationError("Metadata must be a dictionary")

    sanitized = {}
    for key, value in metadata.items():
        try:
            # Sanitize keys
            safe_key = sanitize_string(str(key), max_length=50)

            # Sanitize values
            if isinstance(value, str):
                safe_value = sanitize_string(value, max_length=255)
            elif isinstance(value, (int, float, bool)):
                safe_value = value
            else:
                safe_value = str(value)

            sanitized[safe_key] = safe_value
        except Exception:
            # Skip problematic entries
            continue

    return sanitized