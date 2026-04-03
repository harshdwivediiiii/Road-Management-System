from mongoengine import Document, StringField, DateTimeField, URLField
from datetime import datetime

class Hazard(Document):
    """
    MongoDB Document schema based on dashboard data requirements.
    """
    hazard_type = StringField(required=True, default="Pothole")
    zone = StringField(required=True)
    address = StringField(required=True)
    
    # Severity and Status use specific choices to ensure data consistency
    severity = StringField(
        required=True, 
        choices=["High", "Medium", "Low"]
    )
    status = StringField(
        required=True, 
        choices=["Pending", "In Progress", "Fixed"], 
        default="Pending"
    )
    
    # maps_link stores the URL for the external map view
    maps_link = URLField(required=True)
    
    # timestamp stores the detection time as a proper DateTime object
    timestamp = DateTimeField(required=True, default=datetime.utcnow)

    meta = {
        'collection': 'hazards',  # Explicitly naming the collection
        'indexes': [
            'status',
            'zone',
            'severity',
            '-timestamp' # Index for fast sorting by newest first
        ]
    }