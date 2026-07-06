from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
import logging
from datetime import datetime
import uuid
import traceback

from database_shop_chat import (
    SessionLocalShopChat, 
    Conversation, 
    DirectMessage, 
    BlockedUser,
    ContentModeration
)
from datetime import datetime
from security.validators import SecurityUtils, InputValidator, ValidationError
from utils.logging_config import get_logger

logger = get_logger(__file__)

dm_api = Blueprint('dm_api', __name__)

def check_blocked(session, user1_id, user2_id):
    blocked = session.query(BlockedUser).filter(
        or_(
            and_(BlockedUser.BlockerID == user1_id, BlockedUser.BlockedUserID == user2_id),
            and_(BlockedUser.BlockerID == user2_id, BlockedUser.BlockedUserID == user1_id)
        )
    ).first()
    return blocked is not None

def check_user_banned(session, user_id):
    active_ban = session.query(ContentModeration).filter(
        ContentModeration.UserID == user_id,
        ContentModeration.IsActive == True,
        ContentModeration.Action.in_(['temp_ban', 'permanent_ban']),
        or_(
            ContentModeration.ExpiresAt == None,
            ContentModeration.ExpiresAt > datetime.utcnow()
        )
    ).first()
    return active_ban is not None

def get_or_create_conversation(session, user1_id, user2_id):
    conversation = session.query(Conversation).filter(
        or_(
            and_(Conversation.User1ID == user1_id, Conversation.User2ID == user2_id),
            and_(Conversation.User1ID == user2_id, Conversation.User2ID == user1_id)
        )
    ).first()
    
    if not conversation:
        conversation = Conversation(
            ConversationID=str(uuid.uuid4()),
            User1ID=user1_id,
            User2ID=user2_id,
            IsActive=True
        )
        session.add(conversation)
        session.flush()
    
    return conversation

@dm_api.route('/chat/conversations', methods=['GET'])
@SecurityUtils.rate_limit(requests=30, window=60)
def get_conversations():
    try:
        user_id = request.args.get('UserID')
        if not user_id:
            return jsonify({
                'success': False,
                'error': 'UserID is required'
            }), 400
        
        session = SessionLocalShopChat()
        try:
            conversations = session.query(Conversation).filter(
                or_(
                    Conversation.User1ID == user_id,
                    Conversation.User2ID == user_id
                ),
                Conversation.IsActive == True
            ).order_by(Conversation.LastMessageAt.desc()).all()
            
            result = []
            for conv in conversations:
                other_user_id = conv.User2ID if conv.User1ID == user_id else conv.User1ID
                
                last_message = session.query(DirectMessage).filter(
                    DirectMessage.ConversationID == conv.ConversationID,
                    DirectMessage.IsDeleted == False
                ).order_by(DirectMessage.CreatedAt.desc()).first()
                
                unread_count = session.query(DirectMessage).filter(
                    DirectMessage.ConversationID == conv.ConversationID,
                    DirectMessage.ReceiverID == user_id,
                    DirectMessage.Status != 'read',
                    DirectMessage.IsDeleted == False
                ).count()
                
                result.append({
                    'ConversationID': conv.ConversationID,
                    'OtherUserID': other_user_id,
                    'LastMessage': {
                        'Message': last_message.Message if last_message else None,
                        'IsEdited': last_message.IsEdited if last_message else False,
                        'CreatedAt': last_message.CreatedAt.isoformat() if last_message else None
                    } if last_message else None,
                    'UnreadCount': unread_count,
                    'LastMessageAt': conv.LastMessageAt.isoformat() if conv.LastMessageAt else None
                })
            
            return jsonify({
                'success': True,
                'conversations': result
            }), 200
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error getting conversations: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@dm_api.route('/chat/conversations/<conversation_id>/messages', methods=['GET'])
@SecurityUtils.rate_limit(requests=50, window=60)
def get_messages(conversation_id):
    try:
        user_id = request.args.get('UserID')
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        
        if not user_id:
            return jsonify({
                'success': False,
                'error': 'UserID is required'
            }), 400
        
        session = SessionLocalShopChat()
        try:
            conversation = session.query(Conversation).filter(
                Conversation.ConversationID == conversation_id
            ).first()
            
            if not conversation:
                return jsonify({
                    'success': False,
                    'error': 'Conversation not found'
                }), 404
            
            if conversation.User1ID != user_id and conversation.User2ID != user_id:
                return jsonify({
                    'success': False,
                    'error': 'Access denied'
                }), 403
            
            if check_blocked(session, user_id, conversation.User1ID if conversation.User2ID == user_id else conversation.User2ID):
                return jsonify({
                    'success': False,
                    'error': 'User is blocked'
                }), 403
            
            messages = session.query(DirectMessage).filter(
                DirectMessage.ConversationID == conversation_id,
                DirectMessage.IsDeleted == False
            ).order_by(DirectMessage.CreatedAt.desc()).limit(limit).offset(offset).all()
            
            result = []
            for message in reversed(messages):
                result.append({
                    'MessageID': message.MessageID,
                    'SenderID': message.SenderID,
                    'ReceiverID': message.ReceiverID,
                    'Message': message.Message,
                    'MessageType': message.MessageType,
                    'Status': message.Status,
                    'IsEdited': message.IsEdited,
                    'EditedAt': message.EditedAt.isoformat() if message.EditedAt else None,
                    'CreatedAt': message.CreatedAt.isoformat()
                })
            
            session.query(DirectMessage).filter(
                DirectMessage.ConversationID == conversation_id,
                DirectMessage.ReceiverID == user_id,
                DirectMessage.Status != 'read'
            ).update({'Status': 'read'})
            session.commit()
            
            return jsonify({
                'success': True,
                'messages': result
            }), 200
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error getting messages: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@dm_api.route('/chat/messages', methods=['POST'])
@SecurityUtils.rate_limit(requests=30, window=60)
def send_message():
    try:
        if not request.is_json:
            raise ValidationError("Content-Type must be application/json", 415)
        
        data = request.get_json()
        sender_id = data.get('SenderID')
        receiver_id = data.get('ReceiverID')
        message_text = data.get('Message')
        message_type = data.get('MessageType', 'text')
        
        if not sender_id or not receiver_id or not message_text:
            return jsonify({
                'success': False,
                'error': 'SenderID, ReceiverID and Message are required'
            }), 400
        
        if sender_id == receiver_id:
            return jsonify({
                'success': False,
                'error': 'Cannot send message to yourself'
            }), 400
        
        session = SessionLocalShopChat()
        try:
            if check_user_banned(session, sender_id):
                return jsonify({
                    'success': False,
                    'error': 'Your account is banned'
                }), 403
            
            if check_user_banned(session, receiver_id):
                return jsonify({
                    'success': False,
                    'error': 'Cannot send message to banned user'
                }), 403
            
            if check_blocked(session, sender_id, receiver_id):
                return jsonify({
                    'success': False,
                    'error': 'User is blocked'
                }), 403
            
            conversation = get_or_create_conversation(session, sender_id, receiver_id)
            
            message = DirectMessage(
                MessageID=str(uuid.uuid4()),
                ConversationID=conversation.ConversationID,
                SenderID=sender_id,
                ReceiverID=receiver_id,
                Message=message_text,
                MessageType=message_type,
                Status='sent'
            )
            session.add(message)
            
            conversation.LastMessageAt = datetime.utcnow()
            session.commit()
            
            return jsonify({
                'success': True,
                'message': {
                    'MessageID': message.MessageID,
                    'ConversationID': conversation.ConversationID,
                    'SenderID': message.SenderID,
                    'ReceiverID': message.ReceiverID,
                    'Message': message.Message,
                    'IsEdited': message.IsEdited,
                    'EditedAt': message.EditedAt.isoformat() if message.EditedAt else None,
                    'CreatedAt': message.CreatedAt.isoformat()
                }
            }), 201
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@dm_api.route('/chat/messages/<message_id>', methods=['PUT'])
@SecurityUtils.rate_limit(requests=30, window=60)
def edit_message(message_id):
    try:
        if not request.is_json:
            raise ValidationError("Content-Type must be application/json", 415)
        
        data = request.get_json()
        user_id = data.get('UserID')
        new_message_text = data.get('Message')
        
        if not user_id or not new_message_text:
            return jsonify({
                'success': False,
                'error': 'UserID and Message are required'
            }), 400
        
        session = SessionLocalShopChat()
        try:
            message = session.query(DirectMessage).filter(
                DirectMessage.MessageID == message_id
            ).first()
            
            if not message:
                return jsonify({
                    'success': False,
                    'error': 'Message not found'
                }), 404
            
            if message.SenderID != user_id:
                return jsonify({
                    'success': False,
                    'error': 'You can only edit your own messages'
                }), 403
            
            if message.IsDeleted:
                return jsonify({
                    'success': False,
                    'error': 'Cannot edit deleted message'
                }), 400
            
            message.Message = new_message_text
            message.IsEdited = True
            message.EditedAt = datetime.utcnow()
            session.commit()
            
            return jsonify({
                'success': True,
                'message': {
                    'MessageID': message.MessageID,
                    'Message': message.Message,
                    'IsEdited': message.IsEdited,
                    'EditedAt': message.EditedAt.isoformat() if message.EditedAt else None,
                    'UpdatedAt': message.UpdatedAt.isoformat()
                }
            }), 200
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error editing message: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@dm_api.route('/chat/messages/<message_id>', methods=['DELETE'])
@SecurityUtils.rate_limit(requests=20, window=60)
def delete_message(message_id):
    try:
        if not request.is_json:
            user_id = request.args.get('UserID')
        else:
            data = request.get_json()
            user_id = data.get('UserID')
        
        if not user_id:
            return jsonify({
                'success': False,
                'error': 'UserID is required'
            }), 400
        
        session = SessionLocalShopChat()
        try:
            message = session.query(DirectMessage).filter(
                DirectMessage.MessageID == message_id
            ).first()
            
            if not message:
                return jsonify({
                    'success': False,
                    'error': 'Message not found'
                }), 404
            
            if message.SenderID != user_id:
                return jsonify({
                    'success': False,
                    'error': 'You can only delete your own messages'
                }), 403
            
            message.IsDeleted = True
            message.Status = 'deleted'
            session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Message deleted'
            }), 200
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error deleting message: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@dm_api.route('/chat/conversations/<conversation_id>', methods=['DELETE'])
@SecurityUtils.rate_limit(requests=10, window=60)
def delete_conversation(conversation_id):
    try:
        user_id = request.args.get('UserID')
        if not user_id:
            if request.is_json:
                data = request.get_json()
                user_id = data.get('UserID')
            else:
                return jsonify({
                    'success': False,
                    'error': 'UserID is required'
                }), 400
        
        session = SessionLocalShopChat()
        try:
            conversation = session.query(Conversation).filter(
                Conversation.ConversationID == conversation_id
            ).first()
            
            if not conversation:
                return jsonify({
                    'success': False,
                    'error': 'Conversation not found'
                }), 404
            
            if conversation.User1ID != user_id and conversation.User2ID != user_id:
                return jsonify({
                    'success': False,
                    'error': 'Access denied'
                }), 403
            
            conversation.IsActive = False
            session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Conversation deleted'
            }), 200
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error deleting conversation: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

