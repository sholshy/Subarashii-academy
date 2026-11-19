import json
import urllib.request
from decimal import Decimal
from typing import Optional, Tuple
from apps.pricing.models import PricingRuleConfig
from apps.pricing.services import PricingService

class ExchangeRateService:
    """
    Servicio de actualización del tipo de cambio USD/CLP desde APIs financieras en tiempo real.
    Utiliza proveedores públicos gratuitos con conmutación por error (fallback):
    1. cl.dolarapi.com (Mercado cambiario chileno en tiempo real: venta/compra observada)
    2. open.er-api.com (Interbancario global en tiempo real)
    3. api.exchangerate-api.com
    4. mindicador.cl (Banco Central de Chile observado)
    """

    HEADERS = {'User-Agent': 'SubarashiiSmartShowcase/1.0 (Store Management)'}

    @classmethod
    def fetch_from_dolarapi_cl(cls) -> Optional[Decimal]:
        """Consulta cl.dolarapi.com para obtener el dólar en vivo del mercado chileno."""
        try:
            req = urllib.request.Request('https://cl.dolarapi.com/v1/cotizaciones/usd', headers=cls.HEADERS)
            with urllib.request.urlopen(req, timeout=5) as res:
                data = json.loads(res.read().decode('utf-8'))
                val = data.get('venta') or data.get('compra')
                if val:
                    return Decimal(f"{float(val):.2f}")
        except Exception as e:
            print(f"[ExchangeRateService] Falló cl.dolarapi.com: {e}")
        return None

    @classmethod
    def fetch_from_open_er(cls) -> Optional[Decimal]:
        try:
            req = urllib.request.Request('https://open.er-api.com/v6/latest/USD', headers=cls.HEADERS)
            with urllib.request.urlopen(req, timeout=5) as res:
                data = json.loads(res.read().decode('utf-8'))
                rate = data.get('rates', {}).get('CLP')
                if rate:
                    return Decimal(f"{rate:.2f}")
        except Exception as e:
            print(f"[ExchangeRateService] Falló open.er-api.com: {e}")
        return None

    @classmethod
    def fetch_from_exchangerate_api(cls) -> Optional[Decimal]:
        try:
            req = urllib.request.Request('https://api.exchangerate-api.com/v4/latest/USD', headers=cls.HEADERS)
            with urllib.request.urlopen(req, timeout=5) as res:
                data = json.loads(res.read().decode('utf-8'))
                rate = data.get('rates', {}).get('CLP')
                if rate:
                    return Decimal(f"{rate:.2f}")
        except Exception as e:
            print(f"[ExchangeRateService] Falló api.exchangerate-api.com: {e}")
        return None

    @classmethod
    def fetch_from_mindicador(cls) -> Optional[Decimal]:
        try:
            req = urllib.request.Request('https://mindicador.cl/api/dolar', headers=cls.HEADERS)
            with urllib.request.urlopen(req, timeout=6) as res:
                data = json.loads(res.read().decode('utf-8'))
                serie = data.get('serie', [])
                if serie and len(serie) > 0:
                    val = serie[0].get('valor')
                    if val:
                        return Decimal(f"{val:.2f}")
        except Exception as e:
            print(f"[ExchangeRateService] Falló mindicador.cl: {e}")
        return None

    @classmethod
    def fetch_current_usd_to_clp(cls) -> Optional[Decimal]:
        """Obtiene la tasa USD a CLP consultando los proveedores en cascada."""
        rate = cls.fetch_from_dolarapi_cl()
        if rate:
            return rate

        rate = cls.fetch_from_open_er()
        if rate:
            return rate

        rate = cls.fetch_from_exchangerate_api()
        if rate:
            return rate

        rate = cls.fetch_from_mindicador()
        if rate:
            return rate

        return None

    @classmethod
    def update_config_rate(cls, auto_recalculate: bool = False) -> Tuple[Optional[Decimal], int]:
        """
        Consulta la API y actualiza la tasa en la configuración activa.
        Retorna (tasa_actualizada, cantidad_cotizaciones_recalculadas).
        """
        new_rate = cls.fetch_current_usd_to_clp()
        if not new_rate:
            return None, 0

        config = PricingService.get_active_config()
        config.usd_to_clp_rate = new_rate
        config.save()

        recalculated_count = 0
        if auto_recalculate:
            recalculated_count = PricingService.recalculate_all_quotes(config)

        return new_rate, recalculated_count
