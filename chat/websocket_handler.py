from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from datetime import datetime
import uuid
import threading
import time

from database_shop_chat import (
    SessionLocalShopChat,
    Conversation,
    DirectMessage,
    BlockedUser,
    ContentModeration
)
from utils.logging_config import get_logger

logger = get_logger(__file__)

socketio = None
typing_users = {}
typing_lock = threading.Lock()

def init_socketio(app):
    global socketio
    try:
        socketio = SocketIO(
            app,
            cors_allowed_origins="*",
            async_mode='eventlet',
            logger=True,
            engineio_logger=True,
            ping_timeout=60,
            ping_interval=25
        )
        return socketio
    except Exception as e:
        logger.error(f"Error initializing SocketIO: {str(e)}")
        return None

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

def get_conversation_room(conversation_id):
    return f"conversation_{conversation_id}"

def register_socketio_events(socketio):
    @socketio.on('connect')
    def handle_connect(auth):
        user_id = auth.get('user_id') if auth else None
        if not user_id:
            logger.warning("Connection attempt without user_id")
            disconnect()
            return False
        
        logger.info(f"User {user_id} connected to WebSocket")
        return True

    @socketio.on('disconnect')
    def handle_disconnect():
        logger.info("Client disconnected from WebSocket")

    @socketio.on('join_conversation')
    def handle_join_conversation(data):
        try:
            user_id = data.get('user_id')
            conversation_id = data.get('conversation_id')
            
            if not user_id or not conversation_id:
                emit('error', {'message': 'user_id and conversation_id are required'})
                return
            
            session = SessionLocalShopChat()
            try:
                conversation = session.query(Conversation).filter(
                    Conversation.ConversationID == conversation_id
                ).first()
                
                if not conversation:
                    emit('error', {'message': 'Conversation not found'})
                    return
                
                if conversation.User1ID != user_id and conversation.User2ID != user_id:
                    emit('error', {'message': 'Access denied'})
                    return
                
                room = get_conversation_room(conversation_id)
                join_room(room)
                
                logger.info(f"User {user_id} joined conversation {conversation_id}")
                emit('joined_conversation', {
                    'conversation_id': conversation_id,
                    'room': room
                })
                
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Error joining conversation: {str(e)}")
            emit('error', {'message': str(e)})

    @socketio.on('leave_conversation')
    def handle_leave_conversation(data):
        try:
            user_id = data.get('user_id')
            conversation_id = data.get('conversation_id')
            
            if not user_id or not conversation_id:
                return
            
            room = get_conversation_room(conversation_id)
            leave_room(room)
            
            with typing_lock:
                typing_key = f"{conversation_id}_{user_id}"
                if typing_key in typing_users:
                    del typing_users[typing_key]
            
            logger.info(f"User {user_id} left conversation {conversation_id}")
            emit('left_conversation', {
                'conversation_id': conversation_id
            })
        except Exception as e:
            logger.error(f"Error leaving conversation: {str(e)}")

    @socketio.on('send_message')
    def handle_send_message(data):
        try:
            sender_id = data.get('sender_id')
            receiver_id = data.get('receiver_id')
            message_text = data.get('message')
            message_type = data.get('message_type', 'text')
            
            if not sender_id or not receiver_id or not message_text:
                emit('error', {'message': 'sender_id, receiver_id and message are required'})
                return
            
            if sender_id == receiver_id:
                emit('error', {'message': 'Cannot send message to yourself'})
                return
            
            session = SessionLocalShopChat()
            try:
                if check_user_banned(session, sender_id):
                    emit('error', {'message': 'Your account is banned'})
                    return
                
                if check_user_banned(session, receiver_id):
                    emit('error', {'message': 'Cannot send message to banned user'})
                    return
                
                if check_blocked(session, sender_id, receiver_id):
                    emit('error', {'message': 'User is blocked'})
                    return
                
                conversation = get_or_create_conversation(session, sender_id, receiver_id)
                
                message = DirectMessage(
                    MessageID=str(uuid.uuid4()),
                    ConversationID=conversation.ConversationID,
                    SenderID=sender_id,
                    ReceiverID=receiver_id,
                    Message=message_text,
                    MessageType=message_type,
                    Status='sent',
                    IsEdited=False
                )
                session.add(message)
                conversation.LastMessageAt = datetime.utcnow()
                session.commit()
                
                room = get_conversation_room(conversation.ConversationID)
                
                message_data = {
                    'message_id': message.MessageID,
                    'conversation_id': conversation.ConversationID,
                    'sender_id': message.SenderID,
                    'receiver_id': message.ReceiverID,
                    'message': message.Message,
                    'message_type': message.MessageType,
                    'status': message.Status,
                    'is_edited': message.IsEdited,
                    'edited_at': message.EditedAt.isoformat() if message.EditedAt else None,
                    'created_at': message.CreatedAt.isoformat()
                }
                
                socketio.emit('new_message', message_data, room=room)
                
                with typing_lock:
                    typing_key = f"{conversation.ConversationID}_{sender_id}"
                    if typing_key in typing_users:
                        del typing_users[typing_key]
                
                logger.info(f"Message sent from {sender_id} to {receiver_id}")
                
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")
            emit('error', {'message': str(e)})

    @socketio.on('typing_start')
    def handle_typing_start(data):
        try:
            user_id = data.get('user_id')
            conversation_id = data.get('conversation_id')
            
            if not user_id or not conversation_id:
                return
            
            session = SessionLocalShopChat()
            try:
                conversation = session.query(Conversation).filter(
                    Conversation.ConversationID == conversation_id
                ).first()
                
                if not conversation:
                    return
                
                if conversation.User1ID != user_id and conversation.User2ID != user_id:
                    return
                
                room = get_conversation_room(conversation_id)
                
                with typing_lock:
                    typing_key = f"{conversation_id}_{user_id}"
                    typing_users[typing_key] = datetime.utcnow()
                
                socketio.emit('user_typing', {
                    'user_id': user_id,
                    'conversation_id': conversation_id,
                    'is_typing': True
                }, room=room, include_self=False)
                
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Error handling typing start: {str(e)}")

    @socketio.on('typing_stop')
    def handle_typing_stop(data):
        try:
            user_id = data.get('user_id')
            conversation_id = data.get('conversation_id')
            
            if not user_id or not conversation_id:
                return
            
            session = SessionLocalShopChat()
            try:
                conversation = session.query(Conversation).filter(
                    Conversation.ConversationID == conversation_id
                ).first()
                
                if not conversation:
                    return
                
                room = get_conversation_room(conversation_id)
                
                with typing_lock:
                    typing_key = f"{conversation_id}_{user_id}"
                    if typing_key in typing_users:
                        del typing_users[typing_key]
                
                socketio.emit('user_typing', {
                    'user_id': user_id,
                    'conversation_id': conversation_id,
                    'is_typing': False
                }, room=room, include_self=False)
                
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Error handling typing stop: {str(e)}")

    @socketio.on('edit_message')
    def handle_edit_message(data):
        try:
            user_id = data.get('user_id')
            message_id = data.get('message_id')
            new_message_text = data.get('message')
            
            if not user_id or not message_id or not new_message_text:
                emit('error', {'message': 'user_id, message_id and message are required'})
                return
            
            session = SessionLocalShopChat()
            try:
                message = session.query(DirectMessage).filter(
                    DirectMessage.MessageID == message_id
                ).first()
                
                if not message:
                    emit('error', {'message': 'Message not found'})
                    return
                
                if message.SenderID != user_id:
                    emit('error', {'message': 'You can only edit your own messages'})
                    return
                
                if message.IsDeleted:
                    emit('error', {'message': 'Cannot edit deleted message'})
                    return
                
                message.Message = new_message_text
                message.IsEdited = True
                message.EditedAt = datetime.utcnow()
                session.commit()
                
                room = get_conversation_room(message.ConversationID)
                
                message_data = {
                    'message_id': message.MessageID,
                    'conversation_id': message.ConversationID,
                    'sender_id': message.SenderID,
                    'receiver_id': message.ReceiverID,
                    'message': message.Message,
                    'message_type': message.MessageType,
                    'status': message.Status,
                    'is_edited': message.IsEdited,
                    'edited_at': message.EditedAt.isoformat() if message.EditedAt else None,
                    'created_at': message.CreatedAt.isoformat(),
                    'updated_at': message.UpdatedAt.isoformat()
                }
                
                socketio.emit('message_edited', message_data, room=room)
                
                logger.info(f"Message {message_id} edited by {user_id}")
                
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Error editing message: {str(e)}")
            emit('error', {'message': str(e)})

    @socketio.on('delete_message')
    def handle_delete_message(data):
        try:
            user_id = data.get('user_id')
            message_id = data.get('message_id')
            
            if not user_id or not message_id:
                emit('error', {'message': 'user_id and message_id are required'})
                return
            
            session = SessionLocalShopChat()
            try:
                message = session.query(DirectMessage).filter(
                    DirectMessage.MessageID == message_id
                ).first()
                
                if not message:
                    emit('error', {'message': 'Message not found'})
                    return
                
                if message.SenderID != user_id:
                    emit('error', {'message': 'You can only delete your own messages'})
                    return
                
                message.IsDeleted = True
                message.Status = 'deleted'
                session.commit()
                
                room = get_conversation_room(message.ConversationID)
                
                socketio.emit('message_deleted', {
                    'message_id': message_id,
                    'conversation_id': message.ConversationID
                }, room=room)
                
                logger.info(f"Message {message_id} deleted by {user_id}")
                
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Error deleting message: {str(e)}")
            emit('error', {'message': str(e)})

def cleanup_typing_indicators():
    while True:
        time.sleep(10)
        current_time = datetime.utcnow()
        with typing_lock:
            keys_to_remove = []
            for key, typing_time in typing_users.items():
                if (current_time - typing_time).total_seconds() > 5:
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del typing_users[key]

typing_cleanup_thread = threading.Thread(target=cleanup_typing_indicators, daemon=True)
typing_cleanup_thread.start()

