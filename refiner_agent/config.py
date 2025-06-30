"""Configuration settings for the Refiner Agent"""
import os

# Model configurations - gemini-2.5-flash-preview-05-20, gemini-2.0-flash
STAR_GENERATOR_MODEL = "gemini-2.0-flash"
STAR_CRITIQUE_MODEL = "gemini-2.0-flash"
STAR_REFINER_MODEL = "gemini-2.0-flash"

# Refinement settings (these can remain configurable via env)
RATING_THRESHOLD = float(os.getenv("RATING_THRESHOLD", "4.6"))
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "3"))