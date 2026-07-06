"""
Chart-specific API endpoints for real-time data
"""
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import engine, Currencies
from database.prices import Price
from security.validators import SecurityUtils
from utils.error_handlers import handle_api_errors, ValidationError
from utils.logging_config import get_logger

logger = get_logger(__file__)

chart_bp = Blueprint('chart_api', __name__)

@chart_bp.route('/chart-data', methods=['POST'])
@SecurityUtils.rate_limit(requests=200, window=60)  # بیشتر برای چارت
@handle_api_errors
def get_chart_data():
    """
    [DEPRECATED] Get optimized data for charts with different time ranges
    
    ⚠️ DEPRECATED: This endpoint requires UserID and is custodial.
    ✅ Use GET /api/v2/chart instead (public, cached, no UserID).
    
    ---
    tags:
      - Charts (Deprecated)
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              Symbol:
                type: string
                description: Cryptocurrency symbol (e.g., BTC)
              FiatCurrency:
                type: string
                description: Fiat currency (default USD)
              timeframe:
                type: string
                description: Chart timeframe (1h, 1d, 1w, 1m, 3m, 1y)
                enum: [1h, 1d, 1w, 1m, 3m, 6m, 1y]
              points:
                type: integer
                description: Maximum number of data points (default 100)
    responses:
      200:
        description: Chart data retrieved successfully
        content:
          application/json:
            schema:
              type: object
              properties:
                success:
                  type: boolean
                chart_data:
                  type: object
                  properties:
                    symbol:
                      type: string
                    fiat:
                      type: string
                    timeframe:
                      type: string
                    data:
                      type: array
                      items:
                        type: object
                        properties:
                          timestamp:
                            type: string
                            format: date-time
                          price:
                            type: number
                          market_cap:
                            type: number
                          volume_24h:
                            type: number
                          change_1h:
                            type: number
                          change_24h:
                            type: number
                          change_7d:
                            type: number
                points_count:
                  type: integer
                timeframe:
                  type: string
                last_updated:
                  type: string
                  format: date-time
    """
    try:
        data = request.get_json() or {}
        
        # Validate input
        symbol = data.get('Symbol')
        if not symbol:
            raise ValidationError("Symbol is required")
        
        fiat = data.get('FiatCurrency', 'USD')
        timeframe = data.get('timeframe', '1d')
        max_points = data.get('points', 100)
        
        # Validate timeframe
        valid_timeframes = ['1h', '1d', '1w', '1m', '3m', '6m', '1y']
        if timeframe not in valid_timeframes:
            raise ValidationError(f"Invalid timeframe. Use: {', '.join(valid_timeframes)}")
        
        logger.info(f"Chart data request: {symbol}-{fiat} for {timeframe}")
        
        # Get symbol ID from new schema
        session = Session(bind=engine)
        try:
            symbol_row = session.execute(text("""
                SELECT id FROM symbols 
                WHERE symbol = :symbol OR name = :symbol
                LIMIT 1
            """), {'symbol': symbol}).first()
            
            if not symbol_row:
                raise ValidationError(f"Currency {symbol} not found")
            
            symbol_id = symbol_row[0]
            
        finally:
            session.close()
        
        # Calculate time range based on timeframe
        end_time = datetime.now()
        time_ranges = {
            '1h': timedelta(hours=1),
            '1d': timedelta(days=1),
            '1w': timedelta(days=7),
            '1m': timedelta(days=30),
            '3m': timedelta(days=90),
            '6m': timedelta(days=180),
            '1y': timedelta(days=365)
        }
        
        start_time = end_time - time_ranges.get(timeframe, timedelta(days=1))
        
        # Get fiat rate
        session = Session(bind=engine)
        try:
            fiat_rate_row = session.execute(text("""
                SELECT rate FROM fiat_rates WHERE quote_currency = :fiat
            """), {'fiat': fiat}).first()
            
            fiat_rate = fiat_rate_row[0] if fiat_rate_row else 1.0
            
            records = session.execute(text("""
                SELECT 
                    timestamp,
                    price * :fiat_rate as price,
                    market_cap,
                    volume_24h
                FROM ticks_recent
                WHERE symbol_id = :symbol_id
                  AND timestamp >= :start_time
                  AND timestamp <= :end_time
                ORDER BY timestamp ASC
                LIMIT :max_points
            """), {
                'symbol_id': symbol_id,
                'start_time': start_time,
                'end_time': end_time,
                'max_points': max_points,
                'fiat_rate': fiat_rate
            }).fetchall()
            
            logger.info(f"Found {len(records)} ticks for {symbol}-{fiat} {timeframe}")
            
            if not records:
                current_price = session.execute(text("""
                    SELECT 
                        cp.price * :fiat_rate as price,
                        cp.market_cap,
                        cp.volume_24h,
                        cp.change_1h,
                        cp.change_24h,
                        cp.change_7d,
                        cp.last_updated
                    FROM current_prices cp
                    WHERE cp.symbol_id = :symbol_id
                """), {'symbol_id': symbol_id, 'fiat_rate': fiat_rate}).first()
                
                if current_price:
                    records = [(
                        current_price[6],
                        current_price[0],
                        current_price[1],
                        current_price[2]
                    )]
                    logger.info(f"No historical data, using current price only")
            
            chart_data = {
                'symbol': symbol,
                'fiat': fiat,
                'timeframe': timeframe,
                'data': []
            }
            
            for record in records:
                chart_data['data'].append({
                    'timestamp': record[0].isoformat() if record[0] else None,
                    'price': float(record[1]) if record[1] else None,
                    'market_cap': float(record[2]) if record[2] else None,
                    'volume_24h': float(record[3]) if record[3] else None
                })
            
            logger.info(f"Returning {len(chart_data['data'])} chart points for {symbol}-{fiat}")
            
            return jsonify({
                'success': True,
                'chart_data': chart_data,
                'points_count': len(chart_data['data']),
                'timeframe': timeframe,
                'last_updated': datetime.now().isoformat(),
                'deprecation_notice': (
                    'This endpoint is deprecated. '
                    'Use GET /api/v2/chart instead — public, cached, non-custodial.'
                ),
            }), 200

        finally:
            session.close()
            
    except ValidationError as e:
        return jsonify({
            'success': False,
            'error_type': 'validation_error',
            'message': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Error in chart data: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error_type': 'internal_error',
            'message': str(e)
        }), 500

@chart_bp.route('/chart-live-update', methods=['POST'])
@SecurityUtils.rate_limit(requests=500, window=60)  # بیشتر برای live updates
@handle_api_errors
def get_live_chart_update():
    """
    [DEPRECATED] Get live price update for charts (current price and market data)
    
    ⚠️ DEPRECATED: This endpoint requires UserID and is custodial.
    ✅ Use GET /api/v2/prices instead (public, cached, no UserID).
    
    ---
    tags:
      - Charts (Deprecated)
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              Symbol:
                type: array
                items:
                  type: string
                description: List of cryptocurrency symbols
              FiatCurrency:
                type: string
                description: Fiat currency (default USD)
    responses:
      200:
        description: Live market data retrieved successfully
        content:
          application/json:
            schema:
              type: object
              properties:
                success:
                  type: boolean
                live_prices:
                  type: object
                  additionalProperties:
                    type: object
                    properties:
                      price:
                        type: number
                      market_cap:
                        type: number
                      volume_24h:
                        type: number
                      change_1h:
                        type: number
                      change_24h:
                        type: number
                      change_7d:
                        type: number
                      last_updated:
                        type: string
                        format: date-time
                fiat_currency:
                  type: string
                timestamp:
                  type: string
                  format: date-time
    """
    try:
        data = request.get_json() or {}
        symbols = data.get('Symbol', [])
        
        if isinstance(symbols, str):
            symbols = [symbols]
        
        if not symbols:
            raise ValidationError("At least one Symbol is required")
        
        fiat = data.get('FiatCurrency', 'USD')
        
        # Get current prices from new schema
        session = Session(bind=engine)
        try:
            results = {}
            
            for symbol in symbols:
                symbol_row = session.execute(text("""
                    SELECT id FROM symbols 
                    WHERE symbol = :symbol OR name = :symbol
                    LIMIT 1
                """), {'symbol': symbol}).first()
                
                if symbol_row:
                    symbol_id = symbol_row[0]
                    
                    price_data = session.execute(text("""
                        SELECT 
                            cp.price,
                            cp.price * COALESCE(fr.rate, 1) as price_fiat,
                            cp.market_cap,
                            cp.volume_24h,
                            cp.change_1h,
                            cp.change_24h,
                            cp.change_7d,
                            cp.last_updated
                        FROM current_prices cp
                        LEFT JOIN fiat_rates fr ON fr.quote_currency = :fiat
                        WHERE cp.symbol_id = :symbol_id
                    """), {'symbol_id': symbol_id, 'fiat': fiat}).first()
                    
                    if price_data:
                        results[symbol] = {
                            'price': float(price_data[1]),
                            'market_cap': float(price_data[2]) if price_data[2] else None,
                            'volume_24h': float(price_data[3]) if price_data[3] else None,
                            'change_1h': float(price_data[4]) if price_data[4] else None,
                            'change_24h': float(price_data[5]) if price_data[5] else None,
                            'change_7d': float(price_data[6]) if price_data[6] else None,
                            'last_updated': price_data[7].isoformat() if price_data[7] else None
                        }
                    else:
                        results[symbol] = None
                else:
                    results[symbol] = None
            
            return jsonify({
                'success': True,
                'live_prices': results,
                'fiat_currency': fiat,
                'timestamp': datetime.now().isoformat()
            }), 200
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Error in live chart update: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error_type': 'internal_error',
            'message': str(e)
        }), 500
