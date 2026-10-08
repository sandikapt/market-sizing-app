run:
	uv run streamlit run streamlit_app.py --server.enableCORS false --server.enableXsrfProtection false

stop:
	pkill -f streamlit || true
