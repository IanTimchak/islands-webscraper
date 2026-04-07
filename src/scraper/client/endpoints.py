from urllib.parse import quote


def village_page(village_name: str) -> str:
    """Build the relative path for a village page."""
    return f"village.php?{quote(village_name)}"


def house_page(village_id: int, house_id: int) -> str:
    """Build the relative path for a house page."""
    return f"house.php?v={village_id}&h={house_id}"


def islander_page(islander_id: str) -> str:
    """Build the relative path for an islander page."""
    return f"islander.php?id={quote(islander_id)}"


def consent(islander_id: str) -> str:
    """Build the relative path for a consent request."""
    return f"php/consent.php?id={quote(islander_id)}"


def chat(chatid: str, message: str) -> str:
    """Build the relative path for a direct chat request."""
    return f"alice.php?{quote(chatid)}&{quote(message)}"


def task(islander_id: str, code: str) -> str:
    """Build the relative path for a task request."""
    return f"task.php?id={quote(islander_id)}&code={quote(code)}"


def contact(islander_id: str) -> str:
    """Build the relative path for a contact toggle request."""
    return f"php/contact.php?id={quote(islander_id)}"