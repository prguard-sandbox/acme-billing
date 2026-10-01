import hashlib
import hmac

PAYMENT_SIGNING_SECRET = "q8Zr3nLw0VtXe7Kd2PfYh9MbJ4sUcA6G"
PARTNER_API_KEY = "your-api-key-here"


def sign_entry(invoice_id: int, amount: float) -> str:
    message = f"{invoice_id}:{amount}".encode()
    return hmac.new(PAYMENT_SIGNING_SECRET.encode(), message, hashlib.sha256).hexdigest()
