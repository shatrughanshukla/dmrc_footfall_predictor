import os
from app import app
import uvicorn

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    reload = os.environ.get('UVICORN_RELOAD', '0').lower() in ('1', 'true', 'yes')
    uvicorn.run('app:app', host='0.0.0.0', port=port, reload=reload)
