"""ByteMe provider service adapter implementation."""

import logging
from typing import List, Dict, Any, Optional
from decimal import Decimal
from io import StringIO
import time

from ...application.interfaces.providers import IByteMe, ProviderStatus, ProviderType
from ...domain.entities.provider_offer import ProviderOffer, ConnectionType, OfferStatus
from ...domain.value_objects.address import Address
from ...shared.exceptions.domain import ProviderUnavailableException, InvalidAddressException

# Try to import high-performance libraries, fall back to standard library
try:
    import polars as pl
    HAS_POLARS = True
except ImportError:
    HAS_POLARS = False


class ByteMeAdapter(IByteMe):
    """ByteMe provider service adapter with CSV parsing capabilities."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize ByteMe adapter."""
        self._logger = logger or logging.getLogger(__name__)
        self._supported_regions = ["DE", "AT", "CH"]
        self._status = ProviderStatus.AVAILABLE
        self._rate_limit_remaining = 1000
        self._call_count = 0
    
    async def get_offers(self, address: Address) -> List[ProviderOffer]:
        """Get internet offers for a specific address."""
        if not await self.validate_address(address):
            raise InvalidAddressException(f"Address not supported by ByteMe: {address.full_address}")
        
        if self._status != ProviderStatus.AVAILABLE:
            raise ProviderUnavailableException(f"ByteMe provider is {self._status.value}")
        
        try:
            # Get CSV data for the address
            csv_data = await self.get_csv_data_for_address(address)
            
            # Parse CSV data into offers
            offers = await self.parse_csv_data(csv_data)
            
            self._call_count += 1
            self._rate_limit_remaining -= 1
            
            self._logger.info(f"ByteMe: Retrieved {len(offers)} offers for {address.full_address}")
            return offers
            
        except Exception as e:
            self._logger.error(f"ByteMe: Failed to get offers for {address.full_address}: {e}")
            raise ProviderUnavailableException(f"ByteMe service error: {str(e)}")
    
    async def parse_csv_data(self, csv_content: str) -> List[ProviderOffer]:
        """Parse CSV data from ByteMe provider using optimized methods."""
        if not csv_content or not csv_content.strip():
            return []
        
        try:
            if HAS_POLARS:
                return await self._parse_csv_with_polars(csv_content)
            else:
                return await self._parse_csv_pure_python(csv_content)
        except Exception as e:
            self._logger.error(f"ByteMe CSV parsing failed: {e}")
            return []
    
    async def _parse_csv_with_polars(self, csv_data: str) -> List[ProviderOffer]:
        """Parse CSV using Polars for high performance."""
        try:
            self._logger.debug("Using Polars for CSV parsing")
            
            df = pl.read_csv(StringIO(csv_data))
            original_count = len(df)
            self._logger.info(f"ByteMe returned {original_count} total offers")
            
            # Deduplicate and clean data
            df_unique = df.unique(subset=['productId'], keep='first')
            unique_count = len(df_unique)
            self._logger.info(f"After deduplication: {unique_count} unique offers")
            
            df_clean = df_unique.with_columns([
                pl.col('speed').cast(pl.Int32, strict=False).fill_null(0).alias('speed_clean'),
                pl.col('monthlyCostInCent').cast(pl.Int32, strict=False).fill_null(0).alias('monthly_cost_clean'),
                pl.col('afterTwoYearsMonthlyCost').cast(pl.Int32, strict=False).fill_null(0).alias('after_two_years_clean'),
                pl.col('durationInMonths').cast(pl.Int32, strict=False).fill_null(0).alias('duration_clean'),
                pl.col('voucherValue').cast(pl.Int32, strict=False).fill_null(0).alias('voucher_value_clean'),
                pl.col('installationService').cast(pl.Utf8).str.to_lowercase().is_in(['true', '1', 'yes']).alias('installation_clean'),
                pl.col('providerName').fill_null('ByteMe').alias('provider_clean'),
                pl.col('connectionType').fill_null('DSL').alias('connection_clean'),
                pl.col('voucherType').fill_null('').alias('voucher_type_clean'),
                pl.col('tv').fill_null('').str.strip_chars().ne('').alias('tv_included_clean')
            ])
            
            offers = []
            for row in df_clean.to_dicts():
                try:
                    # Convert connection type
                    connection_type = self._normalize_connection_type(row['connection_clean'])
                    
                    # Calculate upload speed (assume 10% of download for DSL, 20% for others)
                    download_speed = row['speed_clean']
                    if connection_type == ConnectionType.DSL:
                        upload_speed = max(1, download_speed // 10)
                    else:
                        upload_speed = max(1, download_speed // 5)
                    
                    offer = ProviderOffer(
                        provider_name=row['provider_clean'],
                        product_id=str(row['productId']),
                        speed_download_mbps=download_speed,
                        speed_upload_mbps=upload_speed,
                        monthly_cost_euros=Decimal(row['monthly_cost_clean']) / 100,
                        connection_type=connection_type,
                        contract_duration_months=row['duration_clean'],
                        setup_fee_euros=None,  # Not provided in ByteMe CSV
                        status=OfferStatus.AVAILABLE
                    )
                    
                    # Add additional features
                    offer.add_feature("installation_service", row['installation_clean'])
                    offer.add_feature("tv_included", row['tv_included_clean'])
                    offer.add_feature("voucher_type", row['voucher_type_clean'])
                    offer.add_feature("voucher_value_euros", Decimal(row['voucher_value_clean']) / 100)
                    offer.add_feature("after_two_years_cost_euros", Decimal(row['after_two_years_clean']) / 100)
                    
                    offers.append(offer)
                    
                except Exception as e:
                    self._logger.warning(f"Failed to parse ByteMe offer: {e}")
                    continue
            
            self._logger.info(f"Polars processed {len(offers)} ByteMe offers")
            return offers
            
        except Exception as e:
            self._logger.error(f"Polars parsing failed: {e}")
            return await self._parse_csv_pure_python(csv_data)
    
    async def _parse_csv_pure_python(self, csv_data: str) -> List[ProviderOffer]:
        """Parse CSV using pure Python as fallback."""
        try:
            self._logger.debug("Using pure Python for CSV parsing")
            
            lines = csv_data.strip().split('\n')
            if len(lines) < 2:
                return []
            
            header = [col.strip() for col in lines[0].split(',')]
            col_map = {col: i for i, col in enumerate(header)}
            
            offers = []
            seen_ids = set()
            
            for line in lines[1:]:
                fields = [field.strip() for field in line.split(',')]
                if len(fields) != len(header):
                    continue
                
                product_id = fields[col_map.get('productId', 0)]
                if product_id in seen_ids:
                    continue
                seen_ids.add(product_id)
                
                try:
                    # Extract and validate data
                    provider_name = fields[col_map.get('providerName', 1)] or 'ByteMe'
                    download_speed = self._safe_int(fields[col_map.get('speed', 2)])
                    monthly_cost_cents = self._safe_int(fields[col_map.get('monthlyCostInCent', 3)])
                    connection_type_str = fields[col_map.get('connectionType', 6)] or 'DSL'
                    contract_duration = self._safe_int(fields[col_map.get('durationInMonths', 5)])
                    
                    # Convert connection type
                    connection_type = self._normalize_connection_type(connection_type_str)
                    
                    # Calculate upload speed
                    if connection_type == ConnectionType.DSL:
                        upload_speed = max(1, download_speed // 10)
                    else:
                        upload_speed = max(1, download_speed // 5)
                    
                    offer = ProviderOffer(
                        provider_name=provider_name,
                        product_id=product_id,
                        speed_download_mbps=download_speed,
                        speed_upload_mbps=upload_speed,
                        monthly_cost_euros=Decimal(monthly_cost_cents) / 100,
                        connection_type=connection_type,
                        contract_duration_months=contract_duration,
                        setup_fee_euros=None,
                        status=OfferStatus.AVAILABLE
                    )
                    
                    # Add additional features
                    offer.add_feature("installation_service", self._safe_bool(fields[col_map.get('installationService', 7)]))
                    offer.add_feature("tv_included", bool(fields[col_map.get('tv', 8)].strip()))
                    offer.add_feature("voucher_type", fields[col_map.get('voucherType', 10)] or '')
                    offer.add_feature("voucher_value_euros", Decimal(self._safe_int(fields[col_map.get('voucherValue', 11)])) / 100)
                    
                    offers.append(offer)
                    
                except Exception as e:
                    self._logger.warning(f"Failed to parse ByteMe offer line: {e}")
                    continue
            
            self._logger.info(f"Pure Python processed {len(offers)} ByteMe offers")
            return offers
            
        except Exception as e:
            self._logger.error(f"Pure Python parsing failed: {e}")
            return []
    
    async def get_csv_data_for_address(self, address: Address) -> str:
        """Get CSV data for a specific address."""
        # In a real implementation, this would make an HTTP request to ByteMe API
        # For now, we'll simulate the response
        self._logger.debug(f"Getting CSV data for address: {address.full_address}")
        
        # This would be replaced with actual API call
        # return await self._make_api_request(address)
        
        # Mock CSV data for demonstration
        return """productId,providerName,speed,monthlyCostInCent,afterTwoYearsMonthlyCost,durationInMonths,connectionType,installationService,tv,voucherType,voucherValue
byteme_dsl_25,ByteMe,25,2999,3499,12,DSL,true,,percentage,500
byteme_dsl_50,ByteMe,50,3999,4499,24,DSL,true,Premium TV,absolute,1000
byteme_cable_100,ByteMe,100,4999,5499,12,Cable,false,,percentage,800"""
    
    async def validate_address(self, address: Address) -> bool:
        """Validate if an address is supported by ByteMe."""
        if address.country not in self._supported_regions:
            return False
        
        # Additional validation logic could be added here
        # For example, checking postal code ranges
        
        return True
    
    async def get_provider_status(self) -> ProviderStatus:
        """Get current status of ByteMe provider."""
        return self._status
    
    @property
    def provider_name(self) -> str:
        """Get the name of the provider."""
        return "ByteMe"
    
    @property
    def provider_type(self) -> ProviderType:
        """Get the type of the provider."""
        return ProviderType.CSV_BASED
    
    @property
    def supported_regions(self) -> List[str]:
        """Get list of supported regions/countries."""
        return self._supported_regions.copy()
    
    async def get_rate_limit_info(self) -> Dict[str, Any]:
        """Get rate limiting information for ByteMe."""
        return {
            "remaining_requests": self._rate_limit_remaining,
            "total_calls": self._call_count,
            "provider_type": "CSV_BASED"
        }
    
    def _safe_int(self, value: Any, default: int = 0) -> int:
        """Safely convert value to integer."""
        if value is None or value == '':
            return default
        try:
            return int(float(str(value).strip()))
        except (ValueError, TypeError):
            return default
    
    def _safe_bool(self, value: Any) -> bool:
        """Safely convert value to boolean."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower().strip() in ['true', '1', 'yes', 'on']
        return bool(value)
    
    def _normalize_connection_type(self, connection_type: str) -> ConnectionType:
        """Normalize connection type string to ConnectionType enum."""
        if not connection_type:
            return ConnectionType.UNKNOWN
        
        connection_upper = connection_type.upper()
        
        if connection_upper in ['DSL', 'ADSL', 'VDSL']:
            return ConnectionType.DSL
        elif connection_upper in ['CABLE', 'COAX']:
            return ConnectionType.CABLE
        elif connection_upper in ['FIBER', 'FIBRE', 'FTTH', 'FTTB']:
            return ConnectionType.FIBER
        elif connection_upper in ['SATELLITE', 'SAT']:
            return ConnectionType.SATELLITE
        elif connection_upper in ['MOBILE', 'LTE', '5G', '4G']:
            return ConnectionType.MOBILE
        else:
            return ConnectionType.UNKNOWN