from sqlalchemy.orm import Session


class PaymentGateway:
    """Pagamento simulado, sem chamadas a um provedor externo."""

    def charge(self, db: Session, order_id: str, amount: str, method: str) -> dict:
        return {"approved": True, "provider_reference": f"SIM-{order_id[:8]}"}


payment_gateway = PaymentGateway()
