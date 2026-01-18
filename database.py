"""
Database - SQLAlchemy models and connection
"""
from sqlalchemy import create_engine, Column, String, Float, Integer, Boolean, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from loguru import logger
import config

Base = declarative_base()

# ============================================================================
# MODELS
# ============================================================================

class Signal(Base):
    """Stores posted trading signals"""
    __tablename__ = 'signals'
    
    id = Column(Integer, primary_key=True)
    token_address = Column(String, unique=True, index=True)
    symbol = Column(String)
    conviction_score = Column(Integer)
    
    # Signal data
    signal_type = Column(String)  # 'standard', 'ultra_early', etc.
    posted_at = Column(DateTime, default=datetime.utcnow)
    
    # Entry metrics
    entry_price = Column(Float)
    entry_mcap = Column(Float)
    entry_liquidity = Column(Float)
    entry_holders = Column(Integer)
    
    # Scoring breakdown
    smart_wallet_score = Column(Integer, default=0)
    narrative_score = Column(Integer, default=0)
    timing_score = Column(Integer, default=0)
    
    # Smart wallet activity
    kol_buyers = Column(JSON)  # List of KOL wallets that bought
    
    # Narrative tags
    narratives = Column(JSON)  # List of matched narratives
    
    # Performance tracking
    peak_price = Column(Float)
    peak_mcap = Column(Float)
    current_price = Column(Float)
    current_mcap = Column(Float)
    max_gain = Column(Float, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    # Outcome
    outcome = Column(String)  # 'pending', 'win', 'loss', 'break_even'
    final_gain = Column(Float)
    

class SmartWalletActivity(Base):
    """Tracks smart wallet transactions"""
    __tablename__ = 'smart_wallet_activity'
    
    id = Column(Integer, primary_key=True)
    wallet_address = Column(String, index=True)
    wallet_name = Column(String)
    wallet_tier = Column(String)  # 'elite', 'top_kol', etc.
    
    token_address = Column(String, index=True)
    transaction_type = Column(String)  # 'buy', 'sell'
    amount = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    signature = Column(String, unique=True)


class NarrativeTrend(Base):
    """Tracks narrative lifecycle and performance"""
    __tablename__ = 'narrative_trends'
    
    id = Column(Integer, primary_key=True)
    narrative_name = Column(String, unique=True)
    
    # Status
    status = Column(String)  # 'emerging', 'hot', 'cooling', 'dead'
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    
    # Performance
    tokens_tracked = Column(Integer, default=0)
    win_rate = Column(Float, default=0)
    avg_gain = Column(Float, default=0)
    
    # Popularity
    mention_count_24h = Column(Integer, default=0)
    tokens_launched_24h = Column(Integer, default=0)


# ============================================================================
# DATABASE CONNECTION
# ============================================================================

def get_engine():
    """Create database engine"""
    if not config.DATABASE_URL:
        logger.warning("⚠️ No DATABASE_URL set")
        return None
    
    try:
        engine = create_engine(
            config.DATABASE_URL,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10
        )
        return engine
    except Exception as e:
        logger.error(f"❌ Failed to create database engine: {e}")
        return None


def init_db():
    """Initialize database tables"""
    engine = get_engine()
    if engine:
        try:
            Base.metadata.create_all(engine)
            logger.info("✅ Database tables initialized")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize database: {e}")
            return False
    return False


def get_session():
    """Get database session"""
    engine = get_engine()
    if engine:
        SessionLocal = sessionmaker(bind=engine)
        return SessionLocal()
    return None
