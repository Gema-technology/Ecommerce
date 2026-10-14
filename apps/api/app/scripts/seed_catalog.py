"""Wipe non-admin commerce/catalog data and seed categories + brands + products.

Keeps: ADMIN/SUPER_ADMIN users, roles, employees (admin), store_config,
sri_config, quote_pricing_config, locations.

Usage:
  cd apps/api
  python -m app.scripts.seed_catalog
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.modules.catalog.models import Brand, Category, Product, ProductImage
from app.modules.inventory.models import Inventory
from app.modules.inventory.repository import InventoryRepository
from app.modules.pricing.models import PriceCurrency, PriceType, ProductPrice
from app.modules.roles.models import User
from app.shared.slug import normalize_sku, slugify

# Curated Unsplash product-style images by theme (external HTTP URLs).
IMG: dict[str, str] = {
    "keyboard": "https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=800&h=800&fit=crop",
    "mouse": "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=800&h=800&fit=crop",
    "mousepad": "https://images.unsplash.com/photo-1615663245857-ac93bb7c39e7?w=800&h=800&fit=crop",
    "monitor": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=800&h=800&fit=crop",
    "webcam": "https://images.unsplash.com/photo-1628348068343-c6a848d2b6dd?w=800&h=800&fit=crop",
    "mic": "https://images.unsplash.com/photo-1590602847861-f357a9332bbc?w=800&h=800&fit=crop",
    "headphones": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=800&h=800&fit=crop",
    "headset": "https://images.unsplash.com/photo-1618366712010-f4ae9c647dcb?w=800&h=800&fit=crop",
    "speaker": "https://images.unsplash.com/photo-1545454675-3531b543be5d?w=800&h=800&fit=crop",
    "cable": "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=800&h=800&fit=crop",
    "adapter": "https://images.unsplash.com/photo-1625948515291-69613efd103f?w=800&h=800&fit=crop",
    "router": "https://images.unsplash.com/photo-1606904825846-647eb07f5be2?w=800&h=800&fit=crop",
    "usb": "https://images.unsplash.com/photo-1597872200969-2b65d56bd16b?w=800&h=800&fit=crop",
    "ssd": "https://images.unsplash.com/photo-1597872200969-2b65d56bd16b?w=800&h=800&fit=crop",
    "charger": "https://images.unsplash.com/photo-1583863788434-e58a36330cf0?w=800&h=800&fit=crop",
    "ups": "https://images.unsplash.com/photo-1558618047-f4c7c87e2560?w=800&h=800&fit=crop",
    "phone": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=800&h=800&fit=crop",
    "stand": "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=800&h=800&fit=crop",
    "controller": "https://images.unsplash.com/photo-1592840496694-26d035b52b48?w=800&h=800&fit=crop",
    "laptop_stand": "https://images.unsplash.com/photo-1525547719571-a2d4ac8945e2?w=800&h=800&fit=crop",
    "cooling": "https://images.unsplash.com/photo-1587202372775-e229f172b9d7?w=800&h=800&fit=crop",
    "filament": "https://images.unsplash.com/photo-1631549916768-4119b2e5f926?w=800&h=800&fit=crop",
    "printer3d": "https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?w=800&h=800&fit=crop",
    "nozzle": "https://images.unsplash.com/photo-1581092160562-40aa08e78837?w=800&h=800&fit=crop",
    "tools": "https://images.unsplash.com/photo-1530124566582-a618bc2615dc?w=800&h=800&fit=crop",
    "consumable": "https://images.unsplash.com/photo-1565193566173-7a0ee3dbe261?w=800&h=800&fit=crop",
    "figurine": "https://images.unsplash.com/photo-1612198188060-c7c2a3b66eae?w=800&h=800&fit=crop",
    "service": "https://images.unsplash.com/photo-1581092918056-0c4c3acd3789?w=800&h=800&fit=crop",
    "paper": "https://images.unsplash.com/photo-1586281380349-632531db7ed4?w=800&h=800&fit=crop",
    "photo_paper": "https://images.unsplash.com/photo-1452860606245-08befc0ff44b?w=800&h=800&fit=crop",
    "pen": "https://images.unsplash.com/photo-1585336261022-680e295ce3fe?w=800&h=800&fit=crop",
    "notebook": "https://images.unsplash.com/photo-1531346878377-a5be20888e57?w=800&h=800&fit=crop",
    "folder": "https://images.unsplash.com/photo-1568667256549-094345857637?w=800&h=800&fit=crop",
    "stapler": "https://images.unsplash.com/photo-1611224923853-80b023f02d71?w=800&h=800&fit=crop",
    "toner": "https://images.unsplash.com/photo-1612815154858-60aa4c59eaa6?w=800&h=800&fit=crop",
}


def _logo(name: str) -> str:
    return f"https://ui-avatars.com/api/?name={name.replace(' ', '+')}&background=1e293b&color=fff&size=256"


CATEGORY_TREE: list[dict[str, Any]] = [
    {
        "name": "Computación y Tecnología",
        "slug": "computacion-tecnologia",
        "description": "Periféricos, audio, redes, almacenamiento y accesorios tech.",
        "image_url": IMG["monitor"],
        "children": [
            {
                "name": "Periféricos",
                "slug": "perifericos",
                "description": "Teclados, ratones, mousepads, monitores, webcams y micrófonos.",
                "image_url": IMG["keyboard"],
            },
            {
                "name": "Audio",
                "slug": "audio",
                "description": "Audífonos, headsets, parlantes y micrófonos de audio.",
                "image_url": IMG["headphones"],
            },
            {
                "name": "Cables y Adaptadores",
                "slug": "cables-y-adaptadores",
                "description": "USB, HDMI, DisplayPort, USB-C, adaptadores y extensiones.",
                "image_url": IMG["cable"],
            },
            {
                "name": "Conectividad y Redes",
                "slug": "conectividad-y-redes",
                "description": "Wi-Fi, Bluetooth, routers, switches y cables de red.",
                "image_url": IMG["router"],
            },
            {
                "name": "Almacenamiento",
                "slug": "almacenamiento",
                "description": "USB, microSD, discos y SSD externos.",
                "image_url": IMG["ssd"],
            },
            {
                "name": "Energía y Carga",
                "slug": "energia-y-carga",
                "description": "Cargadores, fuentes, regletas, protectores y UPS.",
                "image_url": IMG["charger"],
            },
            {
                "name": "Accesorios para Celulares",
                "slug": "accesorios-para-celulares",
                "description": "Cables, cargadores, soportes, adaptadores y protectores.",
                "image_url": IMG["phone"],
            },
            {
                "name": "Gaming",
                "slug": "gaming",
                "description": "Mouse, teclados, headsets, controles y accesorios gaming.",
                "image_url": IMG["controller"],
            },
            {
                "name": "Accesorios para Computadores",
                "slug": "accesorios-para-computadores",
                "description": "Soportes, bases refrigerantes, organizadores y limpieza.",
                "image_url": IMG["laptop_stand"],
            },
        ],
    },
    {
        "name": "Impresión 3D",
        "slug": "impresion-3d",
        "description": "Filamentos, impresoras, repuestos, herramientas y servicios 3D.",
        "image_url": IMG["printer3d"],
        "children": [
            {
                "name": "Filamentos",
                "slug": "filamentos",
                "description": "PLA, PLA+, PETG, ABS, TPU y filamentos especiales.",
                "image_url": IMG["filament"],
            },
            {
                "name": "Impresoras 3D",
                "slug": "impresoras-3d",
                "description": "Impresoras FDM, resina y accesorios.",
                "image_url": IMG["printer3d"],
            },
            {
                "name": "Repuestos y Componentes",
                "slug": "repuestos-y-componentes",
                "description": "Boquillas, hotends, extrusores, PTFE, ventiladores y placas.",
                "image_url": IMG["nozzle"],
            },
            {
                "name": "Herramientas y Mantenimiento",
                "slug": "herramientas-y-mantenimiento",
                "description": "Espátulas, pinzas, alicates, kits de limpieza y calibración.",
                "image_url": IMG["tools"],
            },
            {
                "name": "Consumibles y Accesorios",
                "slug": "consumibles-y-accesorios",
                "description": "Adhesivos, superficies, secadores y almacenamiento.",
                "image_url": IMG["consumable"],
            },
            {
                "name": "Productos Impresos en 3D",
                "slug": "productos-impresos-en-3d",
                "description": "Figuras, organizadores, soportes, llaveros y decoración.",
                "image_url": IMG["figurine"],
            },
            {
                "name": "Servicios de Impresión 3D",
                "slug": "servicios-de-impresion-3d",
                "description": "Impresión bajo pedido, personalización, piezas y prototipado.",
                "image_url": IMG["service"],
            },
        ],
    },
    {
        "name": "Papelería y Oficina",
        "slug": "papeleria-oficina",
        "description": "Papel, escritura, cuadernos, archivo y consumibles de impresión.",
        "image_url": IMG["paper"],
        "children": [
            {
                "name": "Resmas y Papel",
                "slug": "resmas-y-papel",
                "description": "Papel A4, oficio, carta, colores y reciclado.",
                "image_url": IMG["paper"],
            },
            {
                "name": "Papeles Especiales",
                "slug": "papeles-especiales",
                "description": "Fotográfico, adhesivo, cartulina y manualidades.",
                "image_url": IMG["photo_paper"],
            },
            {
                "name": "Escritura y Marcado",
                "slug": "escritura-y-marcado",
                "description": "Esferos, lápices, marcadores, resaltadores y correctores.",
                "image_url": IMG["pen"],
            },
            {
                "name": "Cuadernos y Libretas",
                "slug": "cuadernos-y-libretas",
                "description": "Cuadernos universitarios, libretas, agendas y blocks.",
                "image_url": IMG["notebook"],
            },
            {
                "name": "Archivo y Organización",
                "slug": "archivo-y-organizacion",
                "description": "Carpetas, archivadores, sobres, separadores y etiquetas.",
                "image_url": IMG["folder"],
            },
            {
                "name": "Suministros de Escritorio",
                "slug": "suministros-de-escritorio",
                "description": "Grapadoras, grapas, clips, tijeras, cintas y pegamentos.",
                "image_url": IMG["stapler"],
            },
            {
                "name": "Consumibles de Impresión",
                "slug": "consumibles-de-impresion",
                "description": "Tinta, tóner, cartuchos y etiquetas para impresoras.",
                "image_url": IMG["toner"],
            },
        ],
    },
]

BRANDS: list[dict[str, Any]] = [
    # Tech — affinity on root computacion-tecnologia
    {"name": "Logitech", "website": "https://www.logitech.com", "roots": ["computacion-tecnologia"]},
    {"name": "Razer", "website": "https://www.razer.com", "roots": ["computacion-tecnologia"]},
    {"name": "Corsair", "website": "https://www.corsair.com", "roots": ["computacion-tecnologia"]},
    {"name": "HyperX", "website": "https://hyperx.com", "roots": ["computacion-tecnologia"]},
    {"name": "Redragon", "website": "https://www.redragonzone.com", "roots": ["computacion-tecnologia"]},
    {"name": "HP", "website": "https://www.hp.com", "roots": ["computacion-tecnologia", "papeleria-oficina"]},
    {"name": "Dell", "website": "https://www.dell.com", "roots": ["computacion-tecnologia"]},
    {"name": "Samsung", "website": "https://www.samsung.com", "roots": ["computacion-tecnologia"]},
    {"name": "Kingston", "website": "https://www.kingston.com", "roots": ["computacion-tecnologia"]},
    {"name": "SanDisk", "website": "https://www.sandisk.com", "roots": ["computacion-tecnologia"]},
    {"name": "TP-Link", "website": "https://www.tp-link.com", "roots": ["computacion-tecnologia"]},
    {"name": "Anker", "website": "https://www.anker.com", "roots": ["computacion-tecnologia"]},
    {"name": "Belkin", "website": "https://www.belkin.com", "roots": ["computacion-tecnologia"]},
    {"name": "Ugreen", "website": "https://www.ugreen.com", "roots": ["computacion-tecnologia"]},
    {"name": "Baseus", "website": "https://www.baseus.com", "roots": ["computacion-tecnologia"]},
    {"name": "Genius", "website": "https://www.geniusnet.com", "roots": ["computacion-tecnologia"]},
    {"name": "Xiaomi", "website": "https://www.mi.com", "roots": ["computacion-tecnologia"]},
    {"name": "APC", "website": "https://www.apc.com", "roots": ["computacion-tecnologia"]},
    {"name": "JBL", "website": "https://www.jbl.com", "roots": ["computacion-tecnologia"]},
    {"name": "Sony", "website": "https://www.sony.com", "roots": ["computacion-tecnologia"]},
    # 3D
    {"name": "eSUN", "website": "https://www.esun3d.com", "roots": ["impresion-3d"]},
    {"name": "Sunlu", "website": "https://www.sunlu.com", "roots": ["impresion-3d"]},
    {"name": "Creality", "website": "https://www.creality.com", "roots": ["impresion-3d"]},
    {"name": "Prusa", "website": "https://www.prusa3d.com", "roots": ["impresion-3d"]},
    {"name": "Bambu Lab", "website": "https://bambulab.com", "roots": ["impresion-3d"]},
    {"name": "Elegoo", "website": "https://www.elegoo.com", "roots": ["impresion-3d"]},
    {"name": "Polymaker", "website": "https://www.polymaker.com", "roots": ["impresion-3d"]},
    {"name": "GEMA 3D", "website": None, "roots": ["impresion-3d"]},
    # Office
    {"name": "Faber-Castell", "website": "https://www.faber-castell.com", "roots": ["papeleria-oficina"]},
    {"name": "Pilot", "website": "https://www.pilotpen.com", "roots": ["papeleria-oficina"]},
    {"name": "BIC", "website": "https://www.bic.com", "roots": ["papeleria-oficina"]},
    {"name": "Norma", "website": "https://www.norma.com", "roots": ["papeleria-oficina"]},
    {"name": "Artesco", "website": None, "roots": ["papeleria-oficina"]},
    {"name": "Stabilo", "website": "https://www.stabilo.com", "roots": ["papeleria-oficina"]},
    {"name": "Post-it", "website": "https://www.post-it.com", "roots": ["papeleria-oficina"]},
    {"name": "Scotch", "website": "https://www.scotchbrand.com", "roots": ["papeleria-oficina"]},
    {"name": "Epson", "website": "https://www.epson.com", "roots": ["papeleria-oficina"]},
    {"name": "Canon", "website": "https://www.canon.com", "roots": ["papeleria-oficina"]},
    {"name": "Scribe", "website": None, "roots": ["papeleria-oficina"]},
    {"name": "Report", "website": None, "roots": ["papeleria-oficina"]},
]

# (sku, name, brand, category_slug, img_key, price, model, short_desc, warranty_months)
PRODUCTS: list[tuple[str, str, str, str, str, str, str, str, int]] = [
    # —— Periféricos ——
    ("LOG-K120", "Teclado Logitech K120 USB", "Logitech", "perifericos", "keyboard", "18.90", "K120", "Teclado USB resistente a derrames.", 12),
    ("LOG-MXKEYS", "Teclado Logitech MX Keys", "Logitech", "perifericos", "keyboard", "99.00", "MX Keys", "Teclado inalámbrico iluminado premium.", 24),
    ("RAZ-HUNTSMAN", "Teclado Razer Huntsman Mini", "Razer", "perifericos", "keyboard", "119.00", "Huntsman Mini", "Teclado mecánico 60% óptico.", 24),
    ("RED-K552", "Teclado Redragon Kumara K552", "Redragon", "perifericos", "keyboard", "39.90", "K552", "Teclado mecánico TKL RGB.", 12),
    ("LOG-M185", "Mouse Logitech M185", "Logitech", "perifericos", "mouse", "12.90", "M185", "Mouse inalámbrico compacto.", 12),
    ("LOG-MXM3", "Mouse Logitech MX Master 3S", "Logitech", "perifericos", "mouse", "99.00", "MX Master 3S", "Mouse ergonómico avanzado.", 24),
    ("RAZ-VIPER", "Mouse Razer Viper V2", "Razer", "perifericos", "mouse", "79.00", "Viper V2", "Mouse ultraligero para precisión.", 24),
    ("GEN-DX120", "Mouse Genius DX-120", "Genius", "perifericos", "mouse", "7.50", "DX-120", "Mouse óptico USB básico.", 6),
    ("COR-MM300", "Mousepad Corsair MM300", "Corsair", "perifericos", "mousepad", "24.90", "MM300", "Mousepad extendido para escritorio.", 12),
    ("RAZ-GOLIATH", "Mousepad Razer Goliathus", "Razer", "perifericos", "mousepad", "19.90", "Goliathus", "Superficie control y velocidad.", 12),
    ("SAM-M27", "Monitor Samsung 27\" IPS", "Samsung", "perifericos", "monitor", "189.00", "S27C310", "Monitor Full HD IPS 75Hz.", 24),
    ("DEL-U2422", "Monitor Dell 24\" Ultrasharp", "Dell", "perifericos", "monitor", "249.00", "U2422H", "Monitor IPS con USB-C hub.", 36),
    ("HP-M24F", "Monitor HP M24f 23.8\"", "HP", "perifericos", "monitor", "149.00", "M24f", "Monitor FHD con bordes finos.", 24),
    ("LOG-C920", "Webcam Logitech C920 HD Pro", "Logitech", "perifericos", "webcam", "69.00", "C920", "Webcam Full HD con micrófonos estéreo.", 12),
    ("LOG-Brio", "Webcam Logitech Brio 4K", "Logitech", "perifericos", "webcam", "179.00", "Brio", "Webcam 4K con HDR y Windows Hello.", 24),
    ("HYX-SOLOCAST", "Micrófono HyperX SoloCast", "HyperX", "perifericos", "mic", "59.00", "SoloCast", "Micrófono USB cardioide plug & play.", 24),
    # —— Audio ——
    ("JBL-TUNE510", "Audífonos JBL Tune 510BT", "JBL", "audio", "headphones", "39.90", "Tune 510BT", "Audífonos on-ear Bluetooth.", 12),
    ("SON-WH1000", "Audífonos Sony WH-CH720N", "Sony", "audio", "headphones", "129.00", "WH-CH720N", "Cancelación de ruido inalámbrica.", 24),
    ("XIA-BUDS4", "Audífonos Xiaomi Redmi Buds 4", "Xiaomi", "audio", "headphones", "34.90", "Buds 4", "True wireless con estuche de carga.", 12),
    ("HYX-CLOUD2", "Headset HyperX Cloud II", "HyperX", "audio", "headset", "89.00", "Cloud II", "Headset gaming 7.1 con micrófono.", 24),
    ("LOG-G735", "Headset Logitech G735", "Logitech", "audio", "headset", "199.00", "G735", "Headset inalámbrico LIGHTSPEED RGB.", 24),
    ("RAZ-KRAKEN", "Headset Razer Kraken V3", "Razer", "audio", "headset", "79.00", "Kraken V3", "Headset con audio espacial THX.", 24),
    ("JBL-FLIP6", "Parlante JBL Flip 6", "JBL", "audio", "speaker", "99.00", "Flip 6", "Parlante portátil resistente al agua.", 12),
    ("SON-SRSXB", "Parlante Sony SRS-XB100", "Sony", "audio", "speaker", "49.00", "SRS-XB100", "Parlante compacto Bluetooth.", 12),
    ("HYX-QUADCAST", "Micrófono HyperX QuadCast S", "HyperX", "audio", "mic", "139.00", "QuadCast S", "Micrófono USB RGB para streaming.", 24),
    # —— Cables y Adaptadores ——
    ("UGR-HDMI2", "Cable HDMI 2.1 Ugreen 2m", "Ugreen", "cables-y-adaptadores", "cable", "14.90", "HDMI 2.1", "Cable 8K/4K HDMI de alta velocidad.", 12),
    ("UGR-USBC3", "Cable USB-C a USB-C 100W 1m", "Ugreen", "cables-y-adaptadores", "cable", "12.90", "USBC-100W", "Cable de carga y datos USB-C.", 12),
    ("ANK-USBA", "Cable Anker USB-A a Lightning 1.8m", "Anker", "cables-y-adaptadores", "cable", "15.90", "PowerLine II", "Cable reforzado para iPhone.", 18),
    ("BEL-DP", "Cable Belkin DisplayPort 1.4 2m", "Belkin", "cables-y-adaptadores", "cable", "22.90", "DP1.4", "Cable DisplayPort 8K.", 12),
    ("UGR-HUB7", "Adaptador Ugreen USB-C Hub 7 en 1", "Ugreen", "cables-y-adaptadores", "adapter", "39.90", "CM512", "HDMI, USB 3.0, SD y PD.", 12),
    ("ANK-ADAPT", "Adaptador Anker USB-C a HDMI", "Anker", "cables-y-adaptadores", "adapter", "19.90", "A8312", "Salida 4K a 60Hz.", 18),
    ("BAS-OTG", "Adaptador Baseus USB-C OTG", "Baseus", "cables-y-adaptadores", "adapter", "8.90", "OTG Mini", "Adaptador USB-C a USB-A.", 6),
    ("UGR-EXT", "Extensión USB 3.0 Ugreen 2m", "Ugreen", "cables-y-adaptadores", "cable", "11.90", "USBA-EXT", "Extensión activa USB 3.0.", 12),
    # —— Conectividad y Redes ——
    ("TPL-AX55", "Router TP-Link Archer AX55", "TP-Link", "conectividad-y-redes", "router", "99.00", "AX55", "Router Wi-Fi 6 dual band AX3000.", 24),
    ("TPL-AX10", "Router TP-Link Archer AX10", "TP-Link", "conectividad-y-redes", "router", "59.00", "AX10", "Router Wi-Fi 6 asequible.", 24),
    ("TPL-UE300", "Adaptador USB Ethernet TP-Link UE300", "TP-Link", "conectividad-y-redes", "adapter", "14.90", "UE300", "Gigabit Ethernet por USB 3.0.", 12),
    ("TPL-UB500", "Adaptador Bluetooth TP-Link UB500", "TP-Link", "conectividad-y-redes", "adapter", "12.90", "UB500", "Dongle Bluetooth 5.0 USB.", 12),
    ("TPL-ARCHERT2U", "Adaptador Wi-Fi TP-Link Archer T2U", "TP-Link", "conectividad-y-redes", "adapter", "16.90", "T2U Plus", "Wi-Fi AC600 con antena.", 12),
    ("TPL-SG105", "Switch TP-Link TL-SG105 5 puertos", "TP-Link", "conectividad-y-redes", "router", "24.90", "SG105", "Switch Gigabit no administrable.", 24),
    ("UGR-CAT6", "Cable de red Ugreen Cat6 5m", "Ugreen", "conectividad-y-redes", "cable", "9.90", "Cat6", "Cable Ethernet Gigabit.", 12),
    ("TPL-SG108", "Switch TP-Link TL-SG108 8 puertos", "TP-Link", "conectividad-y-redes", "router", "34.90", "SG108", "Switch Gigabit 8 puertos.", 24),
    # —— Almacenamiento ——
    ("KIN-DTX64", "Memoria USB Kingston DataTraveler 64GB", "Kingston", "almacenamiento", "usb", "9.90", "DTX 64GB", "USB 3.2 Gen 1 compacta.", 60),
    ("KIN-DTX128", "Memoria USB Kingston 128GB", "Kingston", "almacenamiento", "usb", "14.90", "DTX 128GB", "USB de alta capacidad.", 60),
    ("SND-EXT64", "Tarjeta microSD SanDisk Extreme 64GB", "SanDisk", "almacenamiento", "usb", "12.90", "Extreme 64GB", "UHS-I A2 para móviles y drones.", 60),
    ("SND-EXT128", "Tarjeta microSD SanDisk Extreme 128GB", "SanDisk", "almacenamiento", "usb", "19.90", "Extreme 128GB", "Alta velocidad con adaptador SD.", 60),
    ("SND-SSD1T", "SSD Externo SanDisk Extreme 1TB", "SanDisk", "almacenamiento", "ssd", "109.00", "E61 1TB", "SSD portátil USB-C resistente.", 36),
    ("KIN-XS1T", "SSD Externo Kingston XS1000 1TB", "Kingston", "almacenamiento", "ssd", "99.00", "XS1000", "SSD compacto USB 3.2 Gen 2.", 36),
    ("SAM-T7", "SSD Externo Samsung T7 1TB", "Samsung", "almacenamiento", "ssd", "119.00", "T7 1TB", "SSD portátil con encriptación.", 36),
    ("SND-HDD2T", "Disco Externo SanDisk 2TB USB 3.0", "SanDisk", "almacenamiento", "ssd", "69.00", "Portable 2TB", "HDD portátil para respaldo.", 24),
    # —— Energía y Carga ——
    ("ANK-735", "Cargador Anker 735 GaNPrime 65W", "Anker", "energia-y-carga", "charger", "49.90", "735", "Cargador GaN 3 puertos 65W.", 18),
    ("BAS-65W", "Cargador Baseus GaN 65W", "Baseus", "energia-y-carga", "charger", "29.90", "GaN 65W", "Cargador compacto USB-C dual.", 12),
    ("UGR-100W", "Cargador Ugreen Nexode 100W", "Ugreen", "energia-y-carga", "charger", "59.90", "Nexode 100W", "Carga rápida multipuerto.", 12),
    ("APC-BE600", "UPS APC Back-UPS 600VA", "APC", "energia-y-carga", "ups", "89.00", "BE600M1", "UPS con regulación y USB.", 24),
    ("APC-BR1000", "UPS APC BR1000MS", "APC", "energia-y-carga", "ups", "149.00", "BR1000MS", "UPS sinewave para PCs y NAS.", 36),
    ("BEL-SURGE", "Protector de voltaje Belkin 6 tomas", "Belkin", "energia-y-carga", "ups", "24.90", "SurgePlus", "Regleta con protección y USB.", 24),
    ("ANK-POWST", "Fuente Anker PowerPort Strip", "Anker", "energia-y-carga", "charger", "34.90", "PowerStrip", "Regleta con 3 AC y USB.", 18),
    # —— Accesorios Celulares ——
    ("BAS-CABLE", "Cable Baseus USB-C 60W 1m", "Baseus", "accesorios-para-celulares", "cable", "9.90", "Crystal 60W", "Cable de carga rápida para Android.", 6),
    ("ANK-POW20", "Cargador Anker Nano 20W", "Anker", "accesorios-para-celulares", "charger", "18.90", "Nano 20W", "Cargador compacto PD para celular.", 18),
    ("BAS-SOPM", "Soporte Baseus para celular escritorio", "Baseus", "accesorios-para-celulares", "stand", "14.90", "Desktop Stand", "Soporte ajustable aluminio.", 6),
    ("UGR-MAG", "Soporte Ugreen MagSafe auto", "Ugreen", "accesorios-para-celulares", "stand", "19.90", "MagSafe Car", "Soporte magnético para auto.", 12),
    ("BEL-BOOST", "Adaptador Belkin USB-C a Lightning", "Belkin", "accesorios-para-celulares", "adapter", "24.90", "Connect", "Adaptador certificado MFi.", 12),
    ("BAS-PROT", "Soporte Baseus de escritorio plegable", "Baseus", "accesorios-para-celulares", "stand", "11.90", "Foldable", "Soporte plegable multiángulo.", 6),
    # —— Gaming ——
    ("LOG-G502", "Mouse Gaming Logitech G502 X", "Logitech", "gaming", "mouse", "69.00", "G502 X", "Mouse gaming con sensor HERO.", 24),
    ("RAZ-DEATH", "Mouse Gaming Razer DeathAdder V3", "Razer", "gaming", "mouse", "69.00", "DeathAdder V3", "Mouse ergonómico para FPS.", 24),
    ("RED-M711", "Mouse Gaming Redragon Cobra M711", "Redragon", "gaming", "mouse", "24.90", "M711", "Mouse RGB con 7 botones.", 12),
    ("COR-K70", "Teclado Gaming Corsair K70 RGB", "Corsair", "gaming", "keyboard", "149.00", "K70 RGB", "Teclado mecánico Cherry MX.", 24),
    ("LOG-GPROX", "Teclado Gaming Logitech G Pro X", "Logitech", "gaming", "keyboard", "129.00", "G Pro X", "Teclado TKL con switches intercambiables.", 24),
    ("HYX-CLOUD3", "Headset Gaming HyperX Cloud III", "HyperX", "gaming", "headset", "99.00", "Cloud III", "Headset con micrófono detachable.", 24),
    ("SON-DS5", "Control Sony DualSense PS5", "Sony", "gaming", "controller", "69.00", "DualSense", "Control inalámbrico PS5.", 12),
    ("RAZ-WOLVER", "Control Razer Wolverine V2", "Razer", "gaming", "controller", "99.00", "Wolverine V2", "Control cableado para Xbox/PC.", 12),
    ("COR-HS65", "Headset Corsair HS65 Surround", "Corsair", "gaming", "headset", "79.00", "HS65", "Headset con audio espacial.", 24),
    # —— Accesorios PC ——
    ("UGR-STAND", "Soporte laptop Ugreen aluminio", "Ugreen", "accesorios-para-computadores", "laptop_stand", "29.90", "LP177", "Soporte ergonómico ajustable.", 12),
    ("BEL-COOL", "Base refrigerante Belkin CoolSpot", "Belkin", "accesorios-para-computadores", "cooling", "34.90", "CoolSpot", "Base con ventiladores silenciosos.", 12),
    ("UGR-CABLEM", "Organizadores de cables Ugreen pack", "Ugreen", "accesorios-para-computadores", "cable", "8.90", "Cable Clips", "Kit de clips y canales.", 6),
    ("GEN-CLEAN", "Kit de limpieza Genius 3 en 1", "Genius", "accesorios-para-computadores", "tools", "6.90", "Clean Kit", "Spray, paño y cepillo para pantallas.", 3),
    ("BAS-HUB", "Organizador Baseus para escritorio", "Baseus", "accesorios-para-computadores", "stand", "16.90", "Desk Organizer", "Bandeja organizadora de cables.", 6),
    ("UGR-VERT", "Soporte vertical Ugreen para laptop", "Ugreen", "accesorios-para-computadores", "laptop_stand", "22.90", "LP258", "Soporte vertical ahorra espacio.", 12),
    # —— Filamentos ——
    ("ESU-PLA1", "Filamento eSUN PLA+ 1kg Negro", "eSUN", "filamentos", "filament", "22.90", "PLA+ Black", "PLA+ 1.75mm alto rendimiento.", 0),
    ("ESU-PLA2", "Filamento eSUN PLA+ 1kg Blanco", "eSUN", "filamentos", "filament", "22.90", "PLA+ White", "PLA+ 1.75mm acabado mate.", 0),
    ("SUN-PETG", "Filamento Sunlu PETG 1kg Transparente", "Sunlu", "filamentos", "filament", "24.90", "PETG Clear", "PETG resistente a impactos.", 0),
    ("SUN-ABS", "Filamento Sunlu ABS 1kg Gris", "Sunlu", "filamentos", "filament", "23.90", "ABS Grey", "ABS para piezas técnicas.", 0),
    ("POL-TPU", "Filamento Polymaker PolyFlex TPU 1kg", "Polymaker", "filamentos", "filament", "39.90", "PolyFlex", "TPU flexible 95A.", 0),
    ("ESU-SILK", "Filamento eSUN Silk PLA Dorado", "eSUN", "filamentos", "filament", "26.90", "Silk Gold", "PLA seda efecto metalizado.", 0),
    ("BAM-PLA", "Filamento Bambu Lab PLA Basic 1kg", "Bambu Lab", "filamentos", "filament", "24.90", "PLA Basic", "PLA optimizado para AMS.", 0),
    ("SUN-PLA", "Filamento Sunlu PLA 1kg Rojo", "Sunlu", "filamentos", "filament", "19.90", "PLA Red", "PLA estándar fácil de imprimir.", 0),
    # —— Impresoras 3D ——
    ("CRE-ENDER3", "Impresora 3D Creality Ender-3 V3 SE", "Creality", "impresoras-3d", "printer3d", "229.00", "Ender-3 V3 SE", "Impresora FDM auto-nivelada.", 12),
    ("CRE-K1", "Impresora 3D Creality K1", "Creality", "impresoras-3d", "printer3d", "449.00", "K1", "Impresora FDM de alta velocidad.", 12),
    ("ELE-MARS", "Impresora Resina Elegoo Mars 4", "Elegoo", "impresoras-3d", "printer3d", "229.00", "Mars 4", "Impresora MSLA 9K.", 12),
    ("BAM-A1M", "Impresora 3D Bambu Lab A1 Mini", "Bambu Lab", "impresoras-3d", "printer3d", "299.00", "A1 Mini", "FDM compacta con AMS lite opcional.", 12),
    ("PRU-MK4S", "Impresora 3D Prusa MK4S", "Prusa", "impresoras-3d", "printer3d", "899.00", "MK4S", "Impresora FDM open-source premium.", 24),
    ("ELE-WASHER", "Estación lavado Elegoo Mercury Plus", "Elegoo", "impresoras-3d", "consumable", "129.00", "Mercury Plus", "Lavado y curado para resina.", 12),
    # —— Repuestos ——
    ("CRE-NOZ04", "Boquilla Creality 0.4mm MK8 pack 5", "Creality", "repuestos-y-componentes", "nozzle", "8.90", "Nozzle 0.4", "Boquillas latón 0.4mm.", 0),
    ("CRE-HOT", "Hotend Creality Sprite Pro", "Creality", "repuestos-y-componentes", "nozzle", "49.90", "Sprite Pro", "Hotend direct drive completo.", 6),
    ("PRU-EXTR", "Extrusor Prusa Nextruder kit", "Prusa", "repuestos-y-componentes", "nozzle", "89.00", "Nextruder", "Extrusor de alto flujo.", 12),
    ("CRE-PTFE", "Tubo PTFE Capricorn 1m", "Creality", "repuestos-y-componentes", "nozzle", "9.90", "PTFE", "Tubo PTFE baja fricción.", 0),
    ("CRE-FAN", "Ventilador Creality 4010 24V", "Creality", "repuestos-y-componentes", "cooling", "6.90", "Fan 4010", "Ventilador de capa 24V.", 3),
    ("CRE-PEI", "Placa PEI texturizada Creality 235mm", "Creality", "repuestos-y-componentes", "consumable", "19.90", "PEI 235", "Superficie flexible magnética.", 0),
    # —— Herramientas 3D ——
    ("GEM-SPAT", "Espátula GEMA 3D flexible", "GEMA 3D", "herramientas-y-mantenimiento", "tools", "6.90", "Spatula", "Espátula para retirar piezas.", 0),
    ("GEM-TWEE", "Pinzas GEMA 3D de precisión", "GEMA 3D", "herramientas-y-mantenimiento", "tools", "5.90", "Tweezers", "Pinzas antiestáticas.", 0),
    ("GEM-CUT", "Alicates de corte GEMA 3D", "GEMA 3D", "herramientas-y-mantenimiento", "tools", "7.90", "Flush Cutters", "Corte limpio de soportes.", 0),
    ("GEM-CLEAN", "Kit limpieza boquillas GEMA 3D", "GEMA 3D", "herramientas-y-mantenimiento", "tools", "9.90", "Nozzle Clean", "Agujas y cepillo de latón.", 0),
    ("GEM-CAL", "Kit calibración GEMA 3D", "GEMA 3D", "herramientas-y-mantenimiento", "tools", "14.90", "Cal Kit", "Calibradores y gauges.", 0),
    # —— Consumibles 3D ——
    ("SUN-DRY", "Secador de filamento Sunlu S2", "Sunlu", "consumibles-y-accesorios", "consumable", "59.00", "S2 Dryer", "Secador con control de humedad.", 12),
    ("ESU-GLUE", "Adhesivo de impresión eSUN Magigoo", "eSUN", "consumibles-y-accesorios", "consumable", "14.90", "Magigoo", "Adhesivo para PLA/PETG/ABS.", 0),
    ("CRE-SHEET", "Superficie de impresión Creality glass", "Creality", "consumibles-y-accesorios", "consumable", "24.90", "Glass Bed", "Cama de vidrio templado.", 0),
    ("SUN-BOX", "Caja almacenamiento filamento Sunlu", "Sunlu", "consumibles-y-accesorios", "consumable", "29.90", "Filament Box", "Almacenamiento hermético.", 6),
    # —— Productos impresos ——
    ("GEM-FIG01", "Figura impresa 3D dragón 15cm", "GEMA 3D", "productos-impresos-en-3d", "figurine", "24.90", "Dragon 15", "Figura decorativa PLA.", 0),
    ("GEM-ORG01", "Organizador escritorio impreso 3D", "GEMA 3D", "productos-impresos-en-3d", "figurine", "16.90", "Desk Org", "Organizador para bolígrafos y USB.", 0),
    ("GEM-STAND01", "Soporte auriculares impreso 3D", "GEMA 3D", "productos-impresos-en-3d", "figurine", "18.90", "Headset Stand", "Soporte estable para headset.", 0),
    ("GEM-KEY01", "Llavero personalizado impreso 3D", "GEMA 3D", "productos-impresos-en-3d", "figurine", "4.90", "Keychain", "Llavero con texto personalizable.", 0),
    ("GEM-DEC01", "Decoración pared hexagonal pack 6", "GEMA 3D", "productos-impresos-en-3d", "figurine", "19.90", "Hex Wall", "Paneles decorativos PLA.", 0),
    ("GEM-REP01", "Repuesto personalizado bajo medida", "GEMA 3D", "productos-impresos-en-3d", "figurine", "12.90", "Custom Part", "Pieza impresa según archivo STL.", 0),
    # —— Servicios 3D ——
    ("GEM-SRV-POD", "Servicio impresión 3D bajo pedido", "GEMA 3D", "servicios-de-impresion-3d", "service", "15.00", "POD", "Impresión FDM/resina por gramaje.", 0),
    ("GEM-SRV-CUST", "Servicio personalización 3D", "GEMA 3D", "servicios-de-impresion-3d", "service", "25.00", "Custom", "Diseño y personalización de piezas.", 0),
    ("GEM-SRV-MFG", "Servicio fabricación de piezas", "GEMA 3D", "servicios-de-impresion-3d", "service", "40.00", "Manufacturing", "Producción de lotes pequeños.", 0),
    ("GEM-SRV-PROT", "Servicio prototipado rápido", "GEMA 3D", "servicios-de-impresion-3d", "service", "55.00", "Prototyping", "Prototipo funcional en 48-72h.", 0),
    # —— Papelería: Resmas ——
    ("REP-A4", "Resma papel A4 Report 75g 500 hojas", "Report", "resmas-y-papel", "paper", "5.90", "A4 75g", "Papel bond blanco A4.", 0),
    ("SCR-A4", "Resma papel A4 Scribe 80g", "Scribe", "resmas-y-papel", "paper", "6.50", "A4 80g", "Papel bond premium.", 0),
    ("REP-OFICIO", "Resma papel oficio Report 75g", "Report", "resmas-y-papel", "paper", "6.20", "Oficio 75g", "Papel bond tamaño oficio.", 0),
    ("SCR-CARTA", "Resma papel carta Scribe 75g", "Scribe", "resmas-y-papel", "paper", "5.50", "Carta 75g", "Papel tamaño carta.", 0),
    ("NOR-COLOR", "Resma papel colores Norma A4", "Norma", "resmas-y-papel", "paper", "7.90", "Color Pack", "Papel de colores surtidos.", 0),
    ("REP-RECIC", "Resma papel reciclado Report A4", "Report", "resmas-y-papel", "paper", "6.90", "Eco A4", "Papel reciclado 75g.", 0),
    # —— Papeles especiales ——
    ("HP-PHOTO", "Papel fotográfico HP Glossy A4 50h", "HP", "papeles-especiales", "photo_paper", "12.90", "Glossy A4", "Papel fotográfico brillante.", 0),
    ("CAN-PHOTO", "Papel fotográfico Canon PP-201", "Canon", "papeles-especiales", "photo_paper", "14.90", "PP-201", "Papel fotográfico profesional.", 0),
    ("ART-ADH", "Papel adhesivo Artesco A4 20h", "Artesco", "papeles-especiales", "photo_paper", "4.90", "Adhesive A4", "Hojas adhesivas imprimibles.", 0),
    ("NOR-CART", "Cartulina Norma colores pack 20", "Norma", "papeles-especiales", "photo_paper", "3.90", "Cartulina", "Cartulina A4 surtida.", 0),
    ("ART-CRAFT", "Papel manualidades Artesco pack", "Artesco", "papeles-especiales", "photo_paper", "5.50", "Craft Pack", "Papeles decorativos.", 0),
    # —— Escritura ——
    ("BIC-CRISTAL", "Esferos BIC Cristal azul caja x12", "BIC", "escritura-y-marcado", "pen", "3.90", "Cristal", "Esferos clásicos punta media.", 0),
    ("PIL-G2", "Esfero Pilot G2 0.7 azul", "Pilot", "escritura-y-marcado", "pen", "2.50", "G2 0.7", "Gel retractable suave.", 0),
    ("FAB-GRIP", "Lápices Faber-Castell Grip 2001 x12", "Faber-Castell", "escritura-y-marcado", "pen", "6.90", "Grip 2001", "Lápices HB ergonómicos.", 0),
    ("STA-BOSS", "Resaltadores Stabilo Boss pack 4", "Stabilo", "escritura-y-marcado", "pen", "5.90", "Boss Original", "Resaltadores fluorescentes.", 0),
    ("ART-MARK", "Marcadores Artesco permanentes x8", "Artesco", "escritura-y-marcado", "pen", "4.50", "Permanent", "Marcadores punta fina.", 0),
    ("BIC-CORR", "Corrector BIC Fluid 20ml", "BIC", "escritura-y-marcado", "pen", "2.20", "Correction Fluid", "Corrector líquido con brocha.", 0),
    ("PIL-V5", "Esfero Pilot V5 Hitecpoint negro", "Pilot", "escritura-y-marcado", "pen", "2.80", "V5", "Tinta líquida precisión.", 0),
    # —— Cuadernos ——
    ("NOR-UNI", "Cuaderno universitario Norma 100h", "Norma", "cuadernos-y-libretas", "notebook", "3.50", "Universitario", "Cuaderno rayado espiral.", 0),
    ("SCR-UNI", "Cuaderno universitario Scribe 100h", "Scribe", "cuadernos-y-libretas", "notebook", "3.20", "Universitario", "Cuaderno cuadriculado.", 0),
    ("ART-LIB", "Libreta Artesco bolsillo x3", "Artesco", "cuadernos-y-libretas", "notebook", "4.90", "Pocket", "Libretas pequeñas cosidas.", 0),
    ("NOR-AGEN", "Agenda Norma 2026 ejecutiva", "Norma", "cuadernos-y-libretas", "notebook", "12.90", "Agenda 2026", "Agenda diaria con espiral.", 0),
    ("POS-NOTES", "Block Post-it notas 3x3 pack 5", "Post-it", "cuadernos-y-libretas", "notebook", "8.90", "Super Sticky", "Notas adhesivas surtidas.", 0),
    ("SCR-BLOCK", "Block de notas Scribe A5", "Scribe", "cuadernos-y-libretas", "notebook", "2.90", "A5 Pad", "Block rayado desprendible.", 0),
    # —— Archivo ——
    ("ART-CARP", "Carpeta Artesco oficio con gancho", "Artesco", "archivo-y-organizacion", "folder", "1.80", "Folder Hook", "Carpeta plástica con gancho.", 0),
    ("NOR-ARCH", "Archivador Norma oficio lomo ancho", "Norma", "archivo-y-organizacion", "folder", "4.50", "Binder", "Archivador cartoné.", 0),
    ("ART-SOBRE", "Sobres manila Artesco oficio x50", "Artesco", "archivo-y-organizacion", "folder", "5.90", "Manila", "Sobres kraft oficio.", 0),
    ("NOR-SEP", "Separadores Norma A4 x5 colores", "Norma", "archivo-y-organizacion", "folder", "2.40", "Dividers", "Separadores plásticos.", 0),
    ("ART-ETIQ", "Etiquetas Artesco autoadhesivas", "Artesco", "archivo-y-organizacion", "folder", "1.90", "Labels", "Etiquetas blancas multi-uso.", 0),
    # —— Suministros escritorio ——
    ("ART-GRAP", "Grapadora Artesco metálica", "Artesco", "suministros-de-escritorio", "stapler", "4.90", "Stapler", "Grapadora estándar 26/6.", 0),
    ("ART-GRAPAS", "Grapas Artesco 26/6 caja 1000", "Artesco", "suministros-de-escritorio", "stapler", "1.20", "Staples 26/6", "Caja de grapas.", 0),
    ("ART-CLIPS", "Clips Artesco metálicos caja 100", "Artesco", "suministros-de-escritorio", "stapler", "1.50", "Paper Clips", "Clips plateados.", 0),
    ("ART-TIJ", "Tijeras Artesco oficina 21cm", "Artesco", "suministros-de-escritorio", "stapler", "2.90", "Scissors", "Tijeras de acero inoxidable.", 0),
    ("SCO-TAPE", "Cinta adhesiva Scotch Magic 3/4\"", "Scotch", "suministros-de-escritorio", "stapler", "3.50", "Magic Tape", "Cinta invisible matte.", 0),
    ("ART-PEG", "Pegamento Artesco en barra 40g", "Artesco", "suministros-de-escritorio", "stapler", "1.40", "Glue Stick", "Pegamento en barra no tóxico.", 0),
    # —— Consumibles impresión ——
    ("HP-664", "Cartucho HP 664 Negro", "HP", "consumibles-de-impresion", "toner", "18.90", "664 Black", "Tinta original HP DeskJet.", 0),
    ("HP-664C", "Cartucho HP 664 Tricolor", "HP", "consumibles-de-impresion", "toner", "21.90", "664 Color", "Tinta original tricolor.", 0),
    ("EPS-T664", "Tinta Epson T664 Negro 70ml", "Epson", "consumibles-de-impresion", "toner", "12.90", "T6641", "Botella EcoTank negra.", 0),
    ("CAN-245", "Cartucho Canon PG-245 Negro", "Canon", "consumibles-de-impresion", "toner", "24.90", "PG-245", "Cartucho original Canon.", 0),
    ("HP-85A", "Tóner HP 85A Negro", "HP", "consumibles-de-impresion", "toner", "69.00", "CE285A", "Tóner láser original.", 0),
    ("ART-LABPR", "Etiquetas para impresora Artesco A4", "Artesco", "consumibles-de-impresion", "toner", "6.90", "Print Labels", "Hojas de etiquetas láser/inkjet.", 0),
]


WIPE_TABLES_IN_ORDER = [
    "notification_dispatches",
    "payment_events",
    "payments",
    "inventory_reservations",
    "order_status_events",
    "order_items",
    "orders",
    "order_daily_counters",
    "cart_items",
    "carts",
    "fiscal_documents",
    "quote_items",
    "quotes",
    "quote_number_counters",
    "quote_products",
    "inventory_movements",
    "inventory",
    "product_prices",
    "supplier_products",
    "product_images",
    "products",
    "brand_categories",
    "brands",
    "categories",
    "suppliers",
]


def wipe_non_admin_data(db: Session) -> None:
    for table in WIPE_TABLES_IN_ORDER:
        db.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
        print(f"  truncated {table}")

    # Delete non-admin customers (keep ADMIN / SUPER_ADMIN).
    admin_ids = db.execute(
        text(
            """
            SELECT DISTINCT u.id
            FROM users u
            JOIN user_roles ur ON ur.user_id = u.id
            JOIN roles r ON r.id = ur.role_id
            WHERE r.name IN ('ADMIN', 'SUPER_ADMIN')
            """
        )
    ).fetchall()
    keep_ids = [row[0] for row in admin_ids]
    if keep_ids:
        # Explicit uuid list — avoid ARRAY bind quirks across drivers.
        id_list = ", ".join(f"'{uid}'::uuid" for uid in keep_ids)
        db.execute(text(f"DELETE FROM employees WHERE user_id NOT IN ({id_list})"))
        db.execute(text(f"DELETE FROM user_roles WHERE user_id NOT IN ({id_list})"))
        db.execute(text(f"DELETE FROM users WHERE id NOT IN ({id_list})"))
    else:
        print("WARNING: no admin users found; skipping user wipe")
    db.flush()
    print(f"  kept {len(keep_ids)} admin user(s)")


def seed_categories(db: Session) -> dict[str, Category]:
    by_slug: dict[str, Category] = {}
    for root in CATEGORY_TREE:
        parent = Category(
            name=root["name"],
            slug=root["slug"],
            description=root.get("description"),
            image_url=root.get("image_url"),
            parent_id=None,
            is_active=True,
        )
        db.add(parent)
        db.flush()
        by_slug[parent.slug] = parent
        for child in root.get("children", []):
            node = Category(
                name=child["name"],
                slug=child["slug"],
                description=child.get("description"),
                image_url=child.get("image_url"),
                parent_id=parent.id,
                is_active=True,
            )
            db.add(node)
            db.flush()
            by_slug[node.slug] = node
    print(f"  categories: {len(by_slug)}")
    return by_slug


def seed_brands(db: Session, categories: dict[str, Category]) -> dict[str, Brand]:
    by_name: dict[str, Brand] = {}
    for item in BRANDS:
        brand = Brand(
            name=item["name"],
            slug=slugify(item["name"]),
            description=f"Marca {item['name']}",
            logo_url=_logo(item["name"]),
            website_url=item.get("website"),
            is_active=True,
        )
        brand.categories = [categories[slug] for slug in item["roots"] if slug in categories]
        db.add(brand)
        db.flush()
        by_name[brand.name] = brand
    print(f"  brands: {len(by_name)}")
    return by_name


def seed_products(
    db: Session,
    categories: dict[str, Category],
    brands: dict[str, Brand],
    admin: User,
) -> int:
    location = InventoryRepository(db).ensure_default_location()
    now = datetime.now(UTC)
    count = 0
    for (
        sku,
        name,
        brand_name,
        cat_slug,
        img_key,
        price,
        model,
        short_desc,
        warranty,
    ) in PRODUCTS:
        brand = brands[brand_name]
        category = categories[cat_slug]
        product = Product(
            sku=normalize_sku(sku),
            name=name,
            slug=slugify(name),
            short_description=short_desc,
            description=f"{name}. {short_desc} Marca {brand_name}.",
            model=model,
            brand_id=brand.id,
            category_id=category.id,
            specifications={
                "marca": brand_name,
                "modelo": model,
                "categoria": category.name,
            },
            warranty_months=warranty or None,
            is_active=True,
        )
        db.add(product)
        db.flush()
        db.add(
            ProductImage(
                product_id=product.id,
                url=IMG[img_key],
                alt_text=name,
                sort_order=0,
                is_primary=True,
            )
        )
        db.add(
            ProductPrice(
                product_id=product.id,
                price_type=PriceType.RETAIL.value,
                amount=Decimal(price),
                currency=PriceCurrency.USD.value,
                starts_at=now,
                ends_at=None,
                is_active=True,
                cost_reference=None,
                supplier_product_id=None,
                created_by=admin.id,
            )
        )
        db.add(
            Inventory(
                product_id=product.id,
                location_id=location.id,
                quantity=50,
                reserved_quantity=0,
                reorder_point=5,
                reorder_quantity=20,
            )
        )
        count += 1
    print(f"  products: {count}")
    return count


def get_admin_user(db: Session) -> User:
    row = db.execute(
        text(
            """
            SELECT u.id
            FROM users u
            JOIN user_roles ur ON ur.user_id = u.id
            JOIN roles r ON r.id = ur.role_id
            WHERE r.name IN ('ADMIN', 'SUPER_ADMIN')
            ORDER BY CASE WHEN r.name = 'SUPER_ADMIN' THEN 0 ELSE 1 END, u.created_at
            LIMIT 1
            """
        )
    ).first()
    if row is None:
        raise RuntimeError("No admin user found. Run python -m app.scripts.seed first.")
    user = db.get(User, row[0])
    assert user is not None
    return user


def seed() -> None:
    db = SessionLocal()
    try:
        print("Wiping commerce/catalog data (keeping admins + config)...")
        wipe_non_admin_data(db)

        print("Seeding categories...")
        categories = seed_categories(db)

        print("Seeding brands...")
        brands = seed_brands(db, categories)

        admin = get_admin_user(db)
        print(f"Using admin for prices: {admin.email}")

        print("Seeding products (+ images, prices, inventory)...")
        total = seed_products(db, categories, brands, admin)

        db.commit()
        print(
            f"Done. Seeded {len(categories)} categories, {len(brands)} brands, "
            f"{total} products."
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
