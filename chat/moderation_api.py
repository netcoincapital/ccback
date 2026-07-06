from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session
import logging
import os
from datetime import datetime, timedelta
import uuid
import traceback

from database_shop_chat import (
    SessionLocalShopChat,
    UserReport,
    ContentModeration,
    DirectMessage,
    Conversation
)
from security.validators import SecurityUtils, InputValidator, ValidationError
from utils.logging_config import get_logger

logger = get_logger(__file__)

moderation_api = Blueprint('moderation_api', __name__)

def is_moderator(user_id):
    moderator_ids = []
    moderator_env = os.getenv('MODERATOR_USER_IDS', '')
    if moderator_env:
        moderator_ids = [uid.strip() for uid in moderator_env.split(',')]
    return user_id in moderator_ids

@moderation_api.route('/chat/moderation/reports', methods=['GET'])
@SecurityUtils.rate_limit(requests=30, window=60)
def get_all_reports():
    try:
        moderator_id = request.args.get('ModeratorID')
        status = request.args.get('status', 'pending')
        
        if not moderator_id:
            return jsonify({
                'success': False,
                'error': 'ModeratorID is required'
            }), 400
        
        import os
        if not is_moderator(moderator_id):
            return jsonify({
                'success': False,
                'error': 'Access denied. Moderator privileges required'
            }), 403
        
        session = SessionLocalShopChat()
        try:
            query = session.query(UserReport)
            
            if status:
                query = query.filter(UserReport.Status == status)
            
            reports = query.order_by(UserReport.CreatedAt.desc()).limit(100).all()
            
            result = []
            for report in reports:
                result.append({
                    'ReportID': report.ReportID,
                    'ReporterID': report.ReporterID,
                    'ReportedUserID': report.ReportedUserID,
                    'MessageID': report.MessageID,
                    'Reason': report.Reason,
                    'Description': report.Description,
                    'Status': report.Status,
                    'ModeratorNotes': report.ModeratorNotes,
                    'CreatedAt': report.CreatedAt.isoformat()
                })
            
            return jsonify({
                'success': True,
                'reports': result
            }), 200
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error getting reports: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@moderation_api.route('/chat/moderation/reports/<report_id>/resolve', methods=['POST'])
@SecurityUtils.rate_limit(requests=20, window=60)
def resolve_report(report_id):
    try:
        if not request.is_json:
            raise ValidationError("Content-Type must be application/json", 415)
        
        data = request.get_json()
        moderator_id = data.get('ModeratorID')
        status = data.get('Status')
        notes = data.get('ModeratorNotes')
        action = data.get('Action')
        
        if not moderator_id:
            return jsonify({
                'success': False,
                'error': 'ModeratorID is required'
            }), 400
        
        if not is_moderator(moderator_id):
            return jsonify({
                'success': False,
                'error': 'Access denied. Moderator privileges required'
            }), 403
        
        valid_statuses = ['resolved', 'rejected', 'reviewing']
        if status not in valid_statuses:
            return jsonify({
                'success': False,
                'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
            }), 400
        
        session = SessionLocalShopChat()
        try:
            report = session.query(UserReport).filter(
                UserReport.ReportID == report_id
            ).first()
            
            if not report:
                return jsonify({
                    'success': False,
                    'error': 'Report not found'
                }), 404
            
            report.Status = status
            report.ModeratorNotes = notes
            if status == 'resolved':
                report.ResolvedAt = datetime.utcnow()
            
            if action and report.MessageID:
                message = session.query(DirectMessage).filter(
                    DirectMessage.MessageID == report.MessageID
                ).first()
                
                if message:
                    if action == 'delete':
                        message.IsDeleted = True
                        message.Status = 'deleted'
                    elif action == 'warn':
                        moderation = ContentModeration(
                            ModerationID=str(uuid.uuid4()),
                            UserID=report.ReportedUserID,
                            MessageID=report.MessageID,
                            Action='warning',
                            Reason=notes or report.Reason,
                            ModeratorID=moderator_id
                        )
                        session.add(moderation)
            
            session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Report resolved successfully'
            }), 200
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error resolving report: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@moderation_api.route('/chat/moderation/users/<user_id>/ban', methods=['POST'])
@SecurityUtils.rate_limit(requests=10, window=300)
def ban_user(user_id):
    try:
        if not request.is_json:
            raise ValidationError("Content-Type must be application/json", 415)
        
        data = request.get_json()
        moderator_id = data.get('ModeratorID')
        action = data.get('Action')
        reason = data.get('Reason')
        duration_days = data.get('DurationDays')
        
        if not moderator_id:
            return jsonify({
                'success': False,
                'error': 'ModeratorID is required'
            }), 400
        
        if not is_moderator(moderator_id):
            return jsonify({
                'success': False,
                'error': 'Access denied. Moderator privileges required'
            }), 403
        
        valid_actions = ['temp_ban', 'permanent_ban']
        if action not in valid_actions:
            return jsonify({
                'success': False,
                'error': f'Invalid action. Must be one of: {", ".join(valid_actions)}'
            }), 400
        
        session = SessionLocalShopChat()
        try:
            expires_at = None
            if action == 'temp_ban' and duration_days:
                expires_at = datetime.utcnow() + timedelta(days=duration_days)
            
            moderation = ContentModeration(
                ModerationID=str(uuid.uuid4()),
                UserID=user_id,
                Action=action,
                Reason=reason,
                ModeratorID=moderator_id,
                ExpiresAt=expires_at,
                IsActive=True
            )
            session.add(moderation)
            session.commit()
            
            return jsonify({
                'success': True,
                'message': f'User {action} applied successfully',
                'moderation': {
                    'ModerationID': moderation.ModerationID,
                    'ExpiresAt': moderation.ExpiresAt.isoformat() if moderation.ExpiresAt else None
                }
            }), 201
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error banning user: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@moderation_api.route('/chat/moderation/users/<user_id>/unban', methods=['POST'])
@SecurityUtils.rate_limit(requests=10, window=60)
def unban_user(user_id):
    try:
        if not request.is_json:
            raise ValidationError("Content-Type must be application/json", 415)
        
        data = request.get_json()
        moderator_id = data.get('ModeratorID')
        
        if not moderator_id:
            return jsonify({
                'success': False,
                'error': 'ModeratorID is required'
            }), 400
        
        import os
        if not is_moderator(moderator_id):
            return jsonify({
                'success': False,
                'error': 'Access denied. Moderator privileges required'
            }), 403
        
        session = SessionLocalShopChat()
        try:
            moderations = session.query(ContentModeration).filter(
                ContentModeration.UserID == user_id,
                ContentModeration.IsActive == True,
                ContentModeration.Action.in_(['temp_ban', 'permanent_ban'])
            ).all()
            
            for moderation in moderations:
                moderation.IsActive = False
            
            session.commit()
            
            return jsonify({
                'success': True,
                'message': 'User unbanned successfully'
            }), 200
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error unbanning user: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@moderation_api.route('/chat/moderation/users/<user_id>/status', methods=['GET'])
@SecurityUtils.rate_limit(requests=30, window=60)
def get_user_moderation_status(user_id):
    try:
        session = SessionLocalShopChat()
        try:
            active_moderations = session.query(ContentModeration).filter(
                ContentModeration.UserID == user_id,
                ContentModeration.IsActive == True
            ).all()
            
            result = {
                'UserID': user_id,
                'IsBanned': False,
                'BanExpiresAt': None,
                'Warnings': []
            }
            
            for mod in active_moderations:
                if mod.Action in ['temp_ban', 'permanent_ban']:
                    result['IsBanned'] = True
                    if mod.ExpiresAt:
                        result['BanExpiresAt'] = mod.ExpiresAt.isoformat()
                elif mod.Action == 'warning':
                    result['Warnings'].append({
                        'ModerationID': mod.ModerationID,
                        'Reason': mod.Reason,
                        'CreatedAt': mod.CreatedAt.isoformat()
                    })
            
            return jsonify({
                'success': True,
                'status': result
            }), 200
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error getting user status: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

