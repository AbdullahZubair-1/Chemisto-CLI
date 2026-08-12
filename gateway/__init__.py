"""Chemisto FastAPI LLM Gateway.

This service owns the OpenRouter API key and communication. The Chemisto
CLI never talks to OpenRouter directly - it only talks to this gateway
over HTTP, which keeps provider credentials out of the terminal client.
"""
