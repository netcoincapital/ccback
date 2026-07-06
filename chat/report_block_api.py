from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
import logging
from datetime import datetime
import uuid
import traceback

from database_shop_chat import (
    SessionLocalShopChat,
    UserReport,
    BlockedUser,
    DirectMessage
)
from security.validators import SecurityUtils, InputValidator, ValidationError
from utils.logging_config import get_logger

logger = get_logger(__file__)

report_block_api = Blueprint('report_block_api', __name__)

@report_block_api.route('/chat/report', methods=['POST'])
@SecurityUtils.rate_limit(requests=10, window=300)
def report_user():
    try:
        if not request.is_json:
            raise ValidationError("Content-Type must be application/json", 415)
        
        data = request.get_json()
        reporter_id = data.get('ReporterID')
        reported_user_id = data.get('ReportedUserID')
        message_id = data.get('MessageID')
        reason = data.get('Reason')
        description = data.get('Description')
        
        if not reporter_id or not reported_user_id or not reason:
            return jsonify({
                'success': False,
                'error': 'ReporterID, ReportedUserID and Reason are required'
            }), 400
        
        if reporter_id == reported_user_id:
            return jsonify({
                'success': False,
                'error': 'Cannot report yourself'
            }), 400
        
        valid_reasons = ['spam', 'harassment', 'inappropriate_content', 'fake_account', 'scam', 'other']
        if reason not in valid_reasons:
            return jsonify({
                'success': False,
                'error': f'Invalid reason. Must be one of: {", ".join(valid_reasons)}'
            }), 400
        
        session = SessionLocalShopChat()
        try:
            if message_id:
                message = session.query(DirectMessage).filter(
                    DirectMessage.MessageID == message_id
                ).first()
                
                if not message:
                    return jsonify({
                        'success': False,
                        'error': 'Message not found'
                    }), 404
                
                if message.SenderID != reported_user_id:
                    return jsonify({
                        'success': False,
                        'error': 'Message does not belong to reported user'
                    }), 400
                
                message.IsReported = True
            
            existing_report = session.query(UserReport).filter(
                UserReport.ReporterID == reporter_id,
                UserReport.ReportedUserID == reported_user_id,
                UserReport.MessageID == message_id,
                UserReport.Status == 'pending'
            ).first()
            
            if existing_report:
                return jsonify({
                    'success': False,
                    'error': 'You have already reported this user/message'
                }), 400
            
            report = UserReport(
                ReportID=str(uuid.uuid4()),
                ReporterID=reporter_id,
                ReportedUserID=reported_user_id,
                MessageID=message_id,
                Reason=reason,
                Description=description,
                Status='pending'
            )
            session.add(report)
            session.commit()
            
            return jsonify({
                'success': True,
                'report': {
                    'ReportID': report.ReportID,
                    'Status': report.Status
                }
            }), 201
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error creating report: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@report_block_api.route('/chat/reports', methods=['GET'])
@SecurityUtils.rate_limit(requests=20, window=60)
def get_reports():
    try:
        user_id = request.args.get('UserID')
        status = request.args.get('status', 'pending')
        
        if not user_id:
            return jsonify({
                'success': False,
                'error': 'UserID is required'
            }), 400
        
        session = SessionLocalShopChat()
        try:
            query = session.query(UserReport).filter(
                UserReport.ReporterID == user_id
            )
            
            if status:
                query = query.filter(UserReport.Status == status)
            
            reports = query.order_by(UserReport.CreatedAt.desc()).all()
            
            result = []
            for report in reports:
                result.append({
                    'ReportID': report.ReportID,
                    'ReportedUserID': report.ReportedUserID,
                    'MessageID': report.MessageID,
                    'Reason': report.Reason,
                    'Description': report.Description,
                    'Status': report.Status,
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

@report_block_api.route('/chat/block', methods=['POST'])
@SecurityUtils.rate_limit(requests=10, window=300)
def block_user():
    try:
        if not request.is_json:
            raise ValidationError("Content-Type must be application/json", 415)
        
        data = request.get_json()
        blocker_id = data.get('BlockerID')
        blocked_user_id = data.get('BlockedUserID')
        reason = data.get('Reason')
        
        if not blocker_id or not blocked_user_id:
            return jsonify({
                'success': False,
                'error': 'BlockerID and BlockedUserID are required'
            }), 400
        
        if blocker_id == blocked_user_id:
            return jsonify({
                'success': False,
                'error': 'Cannot block yourself'
            }), 400
        
        session = SessionLocalShopChat()
        try:
            existing_block = session.query(BlockedUser).filter(
                BlockedUser.BlockerID == blocker_id,
                BlockedUser.BlockedUserID == blocked_user_id
            ).first()
            
            if existing_block:
                return jsonify({
                    'success': False,
                    'error': 'User is already blocked'
                }), 400
            
            blocked = BlockedUser(
                BlockID=str(uuid.uuid4()),
                BlockerID=blocker_id,
                BlockedUserID=blocked_user_id,
                Reason=reason
            )
            session.add(blocked)
            session.commit()
            
            return jsonify({
                'success': True,
                'message': 'User blocked successfully'
            }), 201
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error blocking user: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@report_block_api.route('/chat/block', methods=['DELETE'])
@SecurityUtils.rate_limit(requests=10, window=60)
def unblock_user():
    try:
        if not request.is_json:
            raise ValidationError("Content-Type must be application/json", 415)
        
        data = request.get_json()
        blocker_id = data.get('BlockerID')
        blocked_user_id = data.get('BlockedUserID')
        
        if not blocker_id or not blocked_user_id:
            return jsonify({
                'success': False,
                'error': 'BlockerID and BlockedUserID are required'
            }), 400
        
        session = SessionLocalShopChat()
        try:
            blocked = session.query(BlockedUser).filter(
                BlockedUser.BlockerID == blocker_id,
                BlockedUser.BlockedUserID == blocked_user_id
            ).first()
            
            if not blocked:
                return jsonify({
                    'success': False,
                    'error': 'User is not blocked'
                }), 404
            
            session.delete(blocked)
            session.commit()
            
            return jsonify({
                'success': True,
                'message': 'User unblocked successfully'
            }), 200
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error unblocking user: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@report_block_api.route('/chat/blocked-users', methods=['GET'])
@SecurityUtils.rate_limit(requests=20, window=60)
def get_blocked_users():
    try:
        user_id = request.args.get('UserID')
        
        if not user_id:
            return jsonify({
                'success': False,
                'error': 'UserID is required'
            }), 400
        
        session = SessionLocalShopChat()
        try:
            blocked_users = session.query(BlockedUser).filter(
                BlockedUser.BlockerID == user_id
            ).all()
            
            result = []
            for blocked in blocked_users:
                result.append({
                    'BlockID': blocked.BlockID,
                    'BlockedUserID': blocked.BlockedUserID,
                    'Reason': blocked.Reason,
                    'CreatedAt': blocked.CreatedAt.isoformat()
                })
            
            return jsonify({
                'success': True,
                'blocked_users': result
            }), 200
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error getting blocked users: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

