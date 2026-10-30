from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name_sw: Mapped[str] = mapped_column(String(120))
    name_en: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(40))  # soft, water, juice, beer, wine, spirit
    unit: Mapped[str] = mapped_column(String(60))  # e.g. "crate of 24"
    units_per_pack: Mapped[int] = mapped_column(Integer, default=1)  # bottles per crate/case
    is_alcohol: Mapped[bool] = mapped_column(Boolean, default=False)
    cost_price: Mapped[int] = mapped_column(BigInteger, default=0)  # TZS per unit, Owner only
    image_url: Mapped[str | None] = mapped_column(String(500))
    returnable_glass: Mapped[bool] = mapped_column(Boolean, default=False)
    empties_deposit_per_unit: Mapped[int] = mapped_column(BigInteger, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    tiers: Mapped[list["PriceTier"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", order_by="PriceTier.min_qty"
    )


class PriceTier(Base):
    __tablename__ = "price_tiers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    min_qty: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[int] = mapped_column(BigInteger)  # TZS, VAT-inclusive

    product: Mapped[Product] = relationship(back_populates="tiers")


class Package(Base):
    __tablename__ = "packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True)
    name_sw: Mapped[str] = mapped_column(String(80))
    name_en: Mapped[str] = mapped_column(String(80))
    description_sw: Mapped[str] = mapped_column(Text, default="")
    description_en: Mapped[str] = mapped_column(Text, default="")
    base_hours: Mapped[int] = mapped_column(Integer, default=5)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    rules: Mapped[list["PackageRule"]] = relationship(
        back_populates="package", cascade="all, delete-orphan"
    )


class PackageRule(Base):
    __tablename__ = "package_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    package_id: Mapped[int] = mapped_column(ForeignKey("packages.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    # bottles per guest over the package's base_hours
    qty_per_guest: Mapped[float] = mapped_column(Numeric(6, 3))
    per_hour: Mapped[bool] = mapped_column(Boolean, default=False)  # scales with event length

    package: Mapped[Package] = relationship(back_populates="rules")
    product: Mapped[Product] = relationship()


class Addon(Base):
    __tablename__ = "addons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name_sw: Mapped[str] = mapped_column(String(80))
    name_en: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(20))  # cooler | ice | server | bartender
    price: Mapped[int] = mapped_column(BigInteger)  # per unit (per shift for staff)
    owned_capacity: Mapped[int | None] = mapped_column(Integer)  # None = unlimited (e.g. ice)
    replacement_cost: Mapped[int] = mapped_column(BigInteger, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    delivery_fee: Mapped[int] = mapped_column(BigInteger)


class Area(Base):
    __tablename__ = "areas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id"))

    zone: Mapped[Zone] = relationship()


class Venue(Base):
    __tablename__ = "venues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    area_id: Mapped[int] = mapped_column(ForeignKey("areas.id"))
    address: Mapped[str] = mapped_column(String(255), default="")
    lat: Mapped[float | None] = mapped_column(Numeric(9, 6))
    lng: Mapped[float | None] = mapped_column(Numeric(9, 6))

    area: Mapped[Area] = relationship()


class GalleryImage(Base):
    __tablename__ = "gallery_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String(500))
    caption_sw: Mapped[str] = mapped_column(String(200), default="")
    caption_en: Mapped[str] = mapped_column(String(200), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
