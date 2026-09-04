from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, TypeAdapter, model_validator

from .models import OrderStatus


class MovieOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    genre: str
    duration_minutes: int
    rating: str
    language: str
    format: str
    color: str


class ShowtimeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    starts_at: datetime
    room: str
    movie: MovieOut


class PricedItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    price: Decimal


class TicketTypeOut(PricedItemOut):
    detail: str


class ProductOut(PricedItemOut):
    description: str
    category: str
    icon: str


class SeatOut(BaseModel):
    code: str
    accessible: bool
    status: Literal["available", "reserved", "occupied"]


class QuantityIn(BaseModel):
    id: str = Field(min_length=1, max_length=36, pattern=r"^[a-zA-Z0-9_-]+$")
    quantity: int = Field(ge=1, le=20)


class CustomerIn(BaseModel):
    kind: Literal["cpf", "email"]
    value: str = Field(min_length=5, max_length=254)

    @model_validator(mode="after")
    def validate_value(self):
        if self.kind == "email":
            self.value = str(TypeAdapter(EmailStr).validate_python(self.value)).lower()
        else:
            digits = "".join(char for char in self.value if char.isdigit())
            if len(digits) != 11 or len(set(digits)) == 1:
                raise ValueError("CPF inválido")
            def digit(length: int) -> int:
                result = sum(int(digits[i]) * (length + 1 - i) for i in range(length)) * 10 % 11
                return 0 if result == 10 else result
            if digit(9) != int(digits[9]) or digit(10) != int(digits[10]):
                raise ValueError("CPF inválido")
            self.value = digits
        return self


class OrderCreate(BaseModel):
    showtime_id: str = Field(min_length=1, max_length=40, pattern=r"^[a-zA-Z0-9_-]+$")
    seats: list[str] = Field(min_length=1, max_length=20)
    tickets: list[QuantityIn] = Field(min_length=1)
    products: list[QuantityIn] = Field(default_factory=list)
    customer: CustomerIn
    reservation_id: str | None = Field(None, min_length=36, max_length=36)

    @model_validator(mode="after")
    def validate_quantities(self):
        if any(len(seat) > 3 or not seat[:1].isalpha() or not seat[1:].isdigit() for seat in self.seats):
            raise ValueError("Há assentos inválidos")
        if len(set(self.seats)) != len(self.seats):
            raise ValueError("Há assentos repetidos")
        if sum(item.quantity for item in self.tickets) != len(self.seats):
            raise ValueError("A quantidade de ingressos deve ser igual à de assentos")
        for collection in (self.tickets, self.products):
            if len({item.id for item in collection}) != len(collection):
                raise ValueError("Há itens repetidos")
        return self


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    kind: str
    reference_id: str
    name: str
    quantity: int
    unit_price: Decimal


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    code: str
    status: OrderStatus
    total: Decimal
    expires_at: datetime
    created_at: datetime
    paid_at: datetime | None
    payment_method: str | None
    seats: list[str] = Field(default_factory=list)
    items: list[OrderItemOut]


class PaymentIn(BaseModel):
    method: Literal["credit", "debit", "pix"]


class ReservationCreate(BaseModel):
    showtime_id: str = Field(min_length=1, max_length=40, pattern=r"^[a-zA-Z0-9_-]+$")
    seats: list[str] = Field(min_length=1, max_length=20)
    reservation_id: str | None = Field(None, min_length=36, max_length=36)

    @model_validator(mode="after")
    def validate_seats(self):
        normalized = [seat.upper() for seat in self.seats]
        if len(set(normalized)) != len(normalized):
            raise ValueError("Há assentos repetidos")
        if any(len(seat) > 3 or not seat[:1].isalpha() or not seat[1:].isdigit() for seat in normalized):
            raise ValueError("Há assentos inválidos")
        self.seats = normalized
        return self


class ReservationOut(BaseModel):
    id: str
    showtime_id: str
    seats: list[str]
    expires_at: datetime
