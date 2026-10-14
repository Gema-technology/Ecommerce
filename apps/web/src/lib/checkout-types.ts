export const CHECKOUT_STEPS = ["Datos", "Envío", "Revisión", "Pago"] as const;

export type CheckoutStep = (typeof CHECKOUT_STEPS)[number];

/** Ecuador provinces — MVP static list; future: API-driven zones */
export const ECUADOR_PROVINCES = [
  "Azuay",
  "Bolívar",
  "Cañar",
  "Carchi",
  "Chimborazo",
  "Cotopaxi",
  "El Oro",
  "Esmeraldas",
  "Galápagos",
  "Guayas",
  "Imbabura",
  "Loja",
  "Los Ríos",
  "Manabí",
  "Morona Santiago",
  "Napo",
  "Orellana",
  "Pastaza",
  "Pichincha",
  "Santa Elena",
  "Santo Domingo de los Tsáchilas",
  "Sucumbíos",
  "Tungurahua",
  "Zamora Chinchipe",
] as const;

export type EcuadorProvince = (typeof ECUADOR_PROVINCES)[number];

/**
 * Main cities / cabeceras by province (MVP).
 * Not every canton — enough for checkout UX; free text not needed when listed.
 */
export const ECUADOR_CITIES_BY_PROVINCE: Record<EcuadorProvince, readonly string[]> = {
  Azuay: ["Cuenca", "Gualaceo", "Paute", "Sigsig", "Santa Isabel"],
  Bolívar: ["Guaranda", "San Miguel", "Caluma", "Chillanes"],
  Cañar: ["Azogues", "Biblián", "Cañar", "La Troncal"],
  Carchi: ["Tulcán", "San Gabriel", "El Ángel", "Mira"],
  Chimborazo: ["Riobamba", "Guano", "Alausí", "Chambo"],
  Cotopaxi: ["Latacunga", "Salcedo", "Saquisilí", "Pujilí"],
  "El Oro": ["Machala", "Pasaje", "Santa Rosa", "Huaquillas", "Zaruma"],
  Esmeraldas: ["Esmeraldas", "Atacames", "Quinindé", "Muisne"],
  Galápagos: ["Puerto Ayora", "Puerto Baquerizo Moreno", "Puerto Villamil"],
  Guayas: ["Guayaquil", "Durán", "Milagro", "Daule", "Samborondón", "Playas"],
  Imbabura: [
    "Ibarra",
    "Otavalo",
    "Atuntaqui",
    "Cotacachi",
    "Pimampiro",
    "Urcuquí",
  ],
  Loja: ["Loja", "Catamayo", "Cariamanga", "Macará"],
  "Los Ríos": ["Babahoyo", "Quevedo", "Ventanas", "Vinces"],
  Manabí: ["Portoviejo", "Manta", "Chone", "Jipijapa", "Bahía de Caráquez"],
  "Morona Santiago": ["Macas", "Sucúa", "Gualaquiza"],
  Napo: ["Tena", "Archidona", "El Chaco"],
  Orellana: ["Francisco de Orellana (Coca)", "La Joya de los Sachas"],
  Pastaza: ["Puyo", "Mera", "Santa Clara"],
  Pichincha: ["Quito", "Cayambe", "Machachi", "Sangolquí", "Tabacundo"],
  "Santa Elena": ["Santa Elena", "La Libertad", "Salinas"],
  "Santo Domingo de los Tsáchilas": ["Santo Domingo", "La Concordia"],
  Sucumbíos: ["Nueva Loja (Lago Agrio)", "Shushufindi", "Gonzalo Pizarro"],
  Tungurahua: ["Ambato", "Baños", "Pelileo", "Píllaro"],
  "Zamora Chinchipe": ["Zamora", "Yantzaza", "Zumbi"],
};

export function citiesForProvince(province: string): readonly string[] {
  if (!province) return [];
  const key = ECUADOR_PROVINCES.find(
    (p) => p.toLowerCase() === province.trim().toLowerCase(),
  );
  if (!key) return [];
  return ECUADOR_CITIES_BY_PROVINCE[key];
}

export function shippingMethodLabel(method: string): string {
  switch (method) {
    case "free":
      return "Envío gratis";
    case "province_flat":
      return "Envío provincial";
    case "standard":
      return "Envío estándar";
    default:
      return "Envío";
  }
}
