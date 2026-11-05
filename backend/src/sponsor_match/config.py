from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import quote

LOCAL_MODEL = 'sentence-transformers/all-MiniLM-L6-v2@1110a243fdf4706b3f48f1d95db1a4f5529b4d41:chunk-mean-v1'


def load_app_environment():
    """Read only this application's literal .env; never execute shell content."""
    path=Path(__file__).resolve().parents[3]/'.env'
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip() and not line.lstrip().startswith('#') and '=' in line:
                name,value=line.split('=',1)
                os.environ.setdefault(name.strip(),value.strip().strip("\"'"))


def embedding_column(settings):
    if settings.dimensions not in {384,768}:raise ValueError('Supported embedding dimensions: 384 or 768')
    return 'embedding_384' if settings.dimensions==384 else 'embedding'


@dataclass(frozen=True)
class Settings:
    database_url: str = "postgresql://localhost:55432/sponsormatch"
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    extraction_model: str = "gpt-6-luna"
    dimensions: int = 768
    embedding_provider: str = 'openai'
    require_verified_email: bool = False
    api_secret: str = ""
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    environment: str = "development"
    demo_price_gbp: int = 19
    session_days: int = 30
    max_attempts: int = 3
    manual_catalogue_updates: bool = False

    @classmethod
    def from_env(cls):
        load_app_environment()
        provider=os.getenv('EMBEDDING_PROVIDER','local')
        if provider not in {'local','openai'}:raise ValueError('Choose local or openai embeddings')
        database=os.getenv('DATABASE_URL') or os.getenv('SUPABASE_CONNECTION_STRING') or cls.database_url
        password=os.getenv('SUPABASE_DATABASE_PASSWORD','')
        for placeholder in ['[YOUR-PASSWORD]','[YOUR_PASSWORD]','<password>']:
            if password:database=database.replace(placeholder,quote(password,safe=''))
        value = cls(
            database_url=database,
            embedding_provider=provider,
            embedding_model=LOCAL_MODEL if provider=='local' else 'text-embedding-3-small',
            dimensions=384 if provider=='local' else 768,
            require_verified_email=os.getenv('REQUIRE_VERIFIED_EMAIL','true').lower()=='true',
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            api_secret=os.getenv("SPONSORMATCH_API_SECRET", ""),
            supabase_url=os.getenv("SUPABASE_URL", ""),
            supabase_publishable_key=os.getenv("SUPABASE_PUBLISHABLE_KEY", ""),
            environment=os.getenv("SPONSORMATCH_ENV", "development"),
            demo_price_gbp=int(os.getenv("DEMO_ACCESS_PRICE_GBP", "19")),
            manual_catalogue_updates=os.getenv('SPONSORREACH_MANUAL_UPDATES','false').lower()=='true',
        )
        if value.environment == "production" and len(value.api_secret) < 32:
            raise ValueError("Production requires a private SPONSORMATCH_API_SECRET of at least 32 characters")
        return value
