"""
User service for managing Firebase users and storing responses.
"""

import logging
import os
import json
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import auth, firestore
from google.cloud import firestore as gcp_firestore
from typing import Dict, Any, Optional, List, Union

from schemas import (
    FinalResponse, IterationData, STARResponse, Critique, 
    ResponseMetadata, PerformanceMetrics
)

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Set to INFO level to see detailed logs

# Add file handler for persistent logging
try:
    file_handler = logging.FileHandler('firestore_debug.log')
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.info("======= Firestore debugging logger initialized =======")
except Exception as e:
    logger.warning(f"Failed to set up file logging: {e}")

def _get_firestore_client():
    """Get a Firestore client with the correct database."""
    try:
        project_id = os.environ.get('FIREBASE_PROJECT_ID', 'refiner-agent')
        
        # Initialize Firebase Admin SDK if not already done
        if not firebase_admin._apps:
            creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
            if creds_path and os.path.exists(creds_path):
                from firebase_admin import credentials
                firebase_admin.initialize_app(credentials.Certificate(creds_path))
            else:
                firebase_admin.initialize_app()  # Use application default credentials
        
        # Create and return Firestore client with specific database
        # Note: firebase_admin.firestore.client() uses the default database
        # For a custom database, we need to use the google-cloud-firestore Client directly
        return gcp_firestore.Client(project=project_id, database="refiner-agent")
        
    except Exception as e:
        logger.error(f"Failed to create Firestore client: {e}")
        raise

def get_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
    """Get user profile from Firestore. If profile doesn't exist, creates a basic one."""
    try:
        db = _get_firestore_client()
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()

        if user_doc.exists:
            return user_doc.to_dict()
        
        # Create new profile if not exists
        try:
            firebase_user = auth.get_user(user_id)
            user_data = {
                'uid': user_id,
                'email': firebase_user.email,
                'displayName': firebase_user.display_name or firebase_user.email.split('@')[0],
                'photoURL': firebase_user.photo_url,
                'createdAt': gcp_firestore.SERVER_TIMESTAMP,
                'lastLogin': gcp_firestore.SERVER_TIMESTAMP
            }
            user_ref.set(user_data)
            return user_data
        except Exception as e:
            logger.error(f"Error creating user profile: {e}")
            return None
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        return None

def update_last_login(user_id: str) -> bool:
    """Update user's last login timestamp."""
    try:
        db = _get_firestore_client()
        db.collection('users').document(user_id).update({
            'lastLogin': gcp_firestore.SERVER_TIMESTAMP
        })
        return True
    except Exception as e:
        logger.error(f"Error updating last login: {e}")
        return False

def store_user_response(user_id: str, response_data: Dict[str, Any]) -> Optional[str]:
    """
    Stores a user's validated STAR response in Firestore.

    This function assumes the incoming response_data has already been validated
    against the FinalResponse Pydantic model.

    Args:
        user_id: The user's authenticated ID.
        response_data: A dictionary conforming to the FinalResponse schema.

    Returns:
        The ID of the newly created document, or None if an error occurred.
    """
    try:
        logger.info(f"--- Storing validated response for user: {user_id} ---")
        db = _get_firestore_client()
        responses_ref = db.collection('responses')

        # The incoming data is trusted as it's validated upstream.
        # We just need to add the server-side timestamp and ensure userId is set.
        final_doc = {
            'userId': user_id,
            'createdAt': datetime.now(timezone.utc).isoformat(),
            'finalResponse': response_data
        }
        
        # Log the structure for verification
        logger.info(f"Final document to be stored (top-level keys): {list(final_doc.keys())}")
        logger.info(f"  - finalResponse keys: {list(final_doc['finalResponse'].keys())}")

        # Add the document to the collection
        _, doc_ref = responses_ref.add(final_doc)
        
        logger.info(f"Successfully stored response with ID {doc_ref.id} for user {user_id}")
        return doc_ref.id

    except Exception as e:
        logger.error(f"Error storing response: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def get_user_responses(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get user's response history from Firestore, ordered by creation date.

    This function retrieves documents, validates them on-read against the
    FinalResponse model, and returns a list of clean, structured response objects.
    """
    try:
        if not user_id or not isinstance(user_id, str):
            logger.error(f"Invalid user_id for retrieval: {user_id}")
            return []

        logger.info(f"Retrieving responses for user_id: {user_id}")
        db = _get_firestore_client()
        docs = db.collection('responses') \
            .where('userId', '==', user_id) \
            .order_by('createdAt', direction=gcp_firestore.Query.DESCENDING) \
            .limit(limit) \
            .stream()

        response_list = []
        for doc in docs:
            doc_data = doc.to_dict()
            response_payload = doc_data.get('finalResponse')

            if not response_payload or not isinstance(response_payload, dict):
                logger.warning(f"Skipping malformed document {doc.id}: missing or invalid 'finalResponse' field.")
                continue

            try:
                response_payload['id'] = doc.id
                validated_response = FinalResponse.model_validate(response_payload)
                response_list.append(validated_response.model_dump())

            except Exception as e:
                logger.error(f"Skipping malformed document {doc.id} due to validation error: {e}")
                continue

        logger.info(f"Successfully retrieved and validated {len(response_list)} responses for user {user_id}")
        return response_list

    except Exception as e:
        logger.error(f"Error getting user responses: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []