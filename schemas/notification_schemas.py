from pydantic import BaseModel, Field, validator
from typing import Optional
import re

class DeviceRegistrationRequest(BaseModel):
    """Schema for device token registration request"""
    UserID: str = Field(
        ..., 
        description="User ID",
        example="123e4567-e89b-12d3-a456-426614174000"
    )
    WalletID: str = Field(
        ...,
        description="Wallet ID",
        example="987e6543-e89b-12d3-a456-426614174000"
    )
    DeviceToken: str = Field(
        ...,
        description="Firebase device token",
        example="fBHZPFJLREyXNK2pNwQlV7:APA91bHgT4BDh5xYP3vd4fg2z..."
    )
    DeviceName: Optional[str] = Field(
        None,
        description="Name of the device",
        example="Samsung Galaxy S21"
    )
    DeviceType: Optional[str] = Field(
        None,
        description="Type of device (android/ios)",
        example="android"
    )
    
    @validator('DeviceToken')
    def validate_device_token(cls, v):
        pattern = r'^[a-zA-Z0-9:_\-]+$'
        if not re.match(pattern, v):
            raise ValueError('فرمت توکن دستگاه نامعتبر است')
        return v
    
    @validator('DeviceType')
    def validate_device_type(cls, v):
        if v and v.lower() not in ['android', 'ios']:
            raise ValueError('نوع دستگاه باید android یا ios باشد')
        return v.lower() if v else v

class DeviceRegistrationResponse(BaseModel):
    """Schema for device token registration response"""
    success: bool = Field(
        ...,
        description="Whether the operation was successful",
        example=True
    )
    message: str = Field(
        ...,
        description="Message describing the result",
        example="Device registered successfully"
    )

class TestNotificationRequest(BaseModel):
    """Schema for test notification request"""
    DeviceToken: str = Field(
        ...,
        description="Firebase device token",
        example="fBHZPFJLREyXNK2pNwQlV7:APA91bHgT4BDh5xYP3vd4fg2z..."
    )
    
    @validator('DeviceToken')
    def validate_device_token(cls, v):
        pattern = r'^[a-zA-Z0-9_-]{152,}$'
        if not re.match(pattern, v):
            raise ValueError('فرمت توکن دستگاه نامعتبر است')
        return v

class TestNotificationResponse(BaseModel):
    """Schema for test notification response"""
    success: bool = Field(
        ...,
        description="Whether the notification was sent successfully",
        example=True
    )
    message: str = Field(
        ...,
        description="Message describing the result",
        example="Test notification sent successfully"
    ) 