from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()


class Settings(BaseModel):
    islands_base_url: str = os.getenv("ISLANDS_BASE_URL", "https://islands.smp.uq.edu.au")
    islands_cookie_header: str = os.getenv("ISLANDS_COOKIE_HEADER", "")
    request_delay_seconds: float = float(os.getenv("REQUEST_DELAY_SECONDS", "2.0"))


settings = Settings()