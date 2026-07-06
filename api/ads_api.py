import os
import uuid
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

from utils.logging_config import get_logger
from database import SessionLocal, Ads
from sqlalchemy import asc, desc

logger = get_logger(__file__)

ads_api = Blueprint('ads_api', __name__)

# ─── Upload config ────────────────────────────────────────────────
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'uploads', 'ads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_IMAGE_SIZE_MB = 5

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def _allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _ad_to_dict(ad: Ads) -> dict:
    """Convert Ads ORM object to JSON-safe dict."""
    return {
        "id": ad.id,
        "title": ad.title,
        "image_url": ad.image_url,
        "backlink": ad.backlink,
        "short_desc": ad.short_desc or "",
        "is_active": ad.is_active,
        "start_date": ad.start_date.isoformat() if ad.start_date else None,
        "end_date": ad.end_date.isoformat() if ad.end_date else None,
        "created_at": ad.created_at.isoformat() if ad.created_at else None,
        "updated_at": ad.updated_at.isoformat() if ad.updated_at else None,
    }


# ═══════════════════════════════════════════════════════════════════
# PUBLIC — دریافت تبلیغات فعال (برای اپلیکیشن)
# ═══════════════════════════════════════════════════════════════════
@ads_api.route('/ads/', methods=['GET'])
def get_active_ads():
    """
    دریافت لیست تبلیغات فعال
    ---
    tags:
      - Ads
    summary: دریافت تبلیغات فعال
    description: تبلیغات فعالی که در بازه زمانی فعلی قرار دارند را برمی‌گرداند
    parameters:
      - name: limit
        in: query
        schema:
          type: integer
          default: 10
        description: تعداد تبلیغات
    responses:
      '200':
        description: لیست تبلیغات
    """
    try:
        limit = request.args.get('limit', default=10, type=int)
        now = datetime.now()

        session = SessionLocal()
        try:
            ads = (
                session.query(Ads)
                .filter(
                    Ads.is_active == True,
                    (Ads.start_date == None) | (Ads.start_date <= now),
                    (Ads.end_date == None) | (Ads.end_date >= now),
                )
                .order_by(asc(Ads.id))
                .limit(limit)
                .all()
            )
            return jsonify({
                "success": True,
                "ads": [_ad_to_dict(a) for a in ads]
            })
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error fetching active ads: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "خطا در دریافت تبلیغات"
        }), 500


# ═══════════════════════════════════════════════════════════════════
# ADMIN — دریافت همه تبلیغات (با امکان فیلتر)
# ═══════════════════════════════════════════════════════════════════
@ads_api.route('/ads/admin', methods=['GET'])
def get_all_ads():
    """
    دریافت همه تبلیغات (پنل مدیریت)
    ---
    tags:
      - Ads
    summary: دریافت همه تبلیغات
    description: همه تبلیغات را بدون فیلتر وضعیت فعال برمی‌گرداند
    parameters:
      - name: skip
        in: query
        schema:
          type: integer
          default: 0
      - name: limit
        in: query
        schema:
          type: integer
          default: 50
    responses:
      '200':
        description: لیست همه تبلیغات
    """
    try:
        skip = request.args.get('skip', default=0, type=int)
        limit = request.args.get('limit', default=50, type=int)

        session = SessionLocal()
        try:
            total = session.query(Ads).count()
            ads = (
                session.query(Ads)
                .order_by(desc(Ads.created_at))
                .offset(skip)
                .limit(limit)
                .all()
            )
            return jsonify({
                "success": True,
                "total": total,
                "ads": [_ad_to_dict(a) for a in ads]
            })
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error fetching all ads: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "خطا در دریافت تبلیغات"
        }), 500


# ═══════════════════════════════════════════════════════════════════
# ADMIN — ایجاد تبلیغ جدید (با آپلود عکس)
# ═══════════════════════════════════════════════════════════════════
@ads_api.route('/ads/', methods=['POST'])
def create_ad():
    """
    ایجاد تبلیغ جدید (پنل مدیریت)
    ---
    tags:
      - Ads
    summary: ایجاد تبلیغ جدید
    description: یک تبلیغ جدید با آپلود عکس ایجاد می‌کند
    requestBody:
      required: true
      content:
        multipart/form-data:
          schema:
            type: object
            properties:
              title:
                type: string
              image:
                type: string
                format: binary
              backlink:
                type: string
              short_desc:
                type: string
              is_active:
                type: boolean
              start_date:
                type: string
                format: date-time
              end_date:
                type: string
                format: date-time
    responses:
      '201':
        description: تبلیغ با موفقیت ایجاد شد
      '400':
        description: خطای اعتبارسنجی
    """
    try:
        title = request.form.get('title', '').strip()
        backlink = request.form.get('backlink', '').strip()
        short_desc = request.form.get('short_desc', '').strip()
        is_active = request.form.get('is_active', 'true').strip().lower() == 'true'
        start_date_str = request.form.get('start_date', '').strip()
        end_date_str = request.form.get('end_date', '').strip()

        # ── Validation ──
        if not title:
            return jsonify({"success": False, "error": "عنوان تبلیغ الزامی است"}), 400
        if not backlink:
            return jsonify({"success": False, "error": "لینک مقصد الزامی است"}), 400

        # ── Parse dates ──
        start_date = None
        if start_date_str:
            try:
                start_date = datetime.fromisoformat(start_date_str)
            except ValueError:
                return jsonify({"success": False, "error": "فرمت start_date نامعتبر است"}), 400

        end_date = None
        if end_date_str:
            try:
                end_date = datetime.fromisoformat(end_date_str)
            except ValueError:
                return jsonify({"success": False, "error": "فرمت end_date نامعتبر است"}), 400

        # ── Handle image upload ──
        image_url = ""
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and _allowed_file(file.filename):
                # Sanitize filename + UUID prefix to avoid collisions
                ext = file.filename.rsplit('.', 1)[1].lower()
                safe_name = f"{uuid.uuid4().hex}.{ext}"
                filepath = os.path.join(UPLOAD_FOLDER, safe_name)
                file.save(filepath)
                image_url = f"/uploads/ads/{safe_name}"
            elif file and file.filename:
                return jsonify({
                    "success": False,
                    "error": "فرمت فایل مجاز نیست. فرمت‌های مجاز: png, jpg, jpeg, gif, webp"
                }), 400
        else:
            return jsonify({"success": False, "error": "آپلود عکس الزامی است"}), 400

        # ── Save to DB ──
        session = SessionLocal()
        try:
            ad = Ads(
                title=title,
                image_url=image_url,
                backlink=backlink,
                short_desc=short_desc or None,
                is_active=is_active,
                start_date=start_date,
                end_date=end_date,
            )
            session.add(ad)
            session.commit()
            session.refresh(ad)

            logger.info(f"Ad created: id={ad.id}, title='{title}'")
            return jsonify({
                "success": True,
                "message": "تبلیغ با موفقیت ایجاد شد",
                "ad": _ad_to_dict(ad)
            }), 201
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    except Exception as e:
        logger.error(f"Error creating ad: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "خطا در ایجاد تبلیغ"
        }), 500


# ═══════════════════════════════════════════════════════════════════
# ADMIN — به‌روزرسانی تبلیغ
# ═══════════════════════════════════════════════════════════════════
@ads_api.route('/ads/<int:ad_id>', methods=['PUT'])
def update_ad(ad_id):
    """
    به‌روزرسانی تبلیغ (پنل مدیریت)
    ---
    tags:
      - Ads
    summary: ویرایش تبلیغ
    parameters:
      - name: ad_id
        in: path
        required: true
        schema:
          type: integer
    requestBody:
      content:
        multipart/form-data:
          schema:
            type: object
            properties:
              title:
                type: string
              image:
                type: string
                format: binary
              backlink:
                type: string
              short_desc:
                type: string
              is_active:
                type: boolean
              start_date:
                type: string
              end_date:
                type: string
    responses:
      '200':
        description: تبلیغ با موفقیت به‌روزرسانی شد
      '404':
        description: تبلیغ یافت نشد
    """
    try:
        session = SessionLocal()
        try:
            ad = session.query(Ads).filter(Ads.id == ad_id).first()
            if not ad:
                return jsonify({"success": False, "error": "تبلیغ یافت نشد"}), 404

            # ── Update fields if provided ──
            title = request.form.get('title', '').strip()
            if title:
                ad.title = title

            backlink = request.form.get('backlink', '').strip()
            if backlink:
                ad.backlink = backlink

            short_desc = request.form.get('short_desc')
            if short_desc is not None:
                ad.short_desc = short_desc.strip() or None

            is_active_str = request.form.get('is_active')
            if is_active_str is not None:
                ad.is_active = is_active_str.strip().lower() == 'true'

            start_date_str = request.form.get('start_date', '').strip()
            if start_date_str:
                try:
                    ad.start_date = datetime.fromisoformat(start_date_str)
                except ValueError:
                    return jsonify({"success": False, "error": "فرمت start_date نامعتبر است"}), 400

            end_date_str = request.form.get('end_date', '').strip()
            if end_date_str:
                try:
                    ad.end_date = datetime.fromisoformat(end_date_str)
                except ValueError:
                    return jsonify({"success": False, "error": "فرمت end_date نامعتبر است"}), 400

            # ── Replace image if new file uploaded ──
            if 'image' in request.files:
                file = request.files['image']
                if file and file.filename and _allowed_file(file.filename):
                    # Delete old image file
                    if ad.image_url and ad.image_url.startswith('/uploads/'):
                        old_path = os.path.join(
                            os.path.dirname(os.path.abspath(__file__)), '..',
                            ad.image_url.lstrip('/')
                        )
                        if os.path.exists(old_path):
                            os.remove(old_path)
                            logger.info(f"Deleted old ad image: {old_path}")

                    # Save new image
                    ext = file.filename.rsplit('.', 1)[1].lower()
                    safe_name = f"{uuid.uuid4().hex}.{ext}"
                    filepath = os.path.join(UPLOAD_FOLDER, safe_name)
                    file.save(filepath)
                    ad.image_url = f"/uploads/ads/{safe_name}"
                elif file and file.filename:
                    return jsonify({
                        "success": False,
                        "error": "فرمت فایل مجاز نیست. فرمت‌های مجاز: png, jpg, jpeg, gif, webp"
                    }), 400

            session.commit()
            session.refresh(ad)
            logger.info(f"Ad updated: id={ad_id}")

            return jsonify({
                "success": True,
                "message": "تبلیغ با موفقیت به‌روزرسانی شد",
                "ad": _ad_to_dict(ad)
            })

        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    except Exception as e:
        logger.error(f"Error updating ad {ad_id}: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "خطا در به‌روزرسانی تبلیغ"
        }), 500


# ═══════════════════════════════════════════════════════════════════
# ADMIN — حذف تبلیغ
# ═══════════════════════════════════════════════════════════════════
@ads_api.route('/ads/<int:ad_id>', methods=['DELETE'])
def delete_ad(ad_id):
    """
    حذف تبلیغ (پنل مدیریت)
    ---
    tags:
      - Ads
    summary: حذف تبلیغ
    parameters:
      - name: ad_id
        in: path
        required: true
        schema:
          type: integer
    responses:
      '200':
        description: تبلیغ با موفقیت حذف شد
      '404':
        description: تبلیغ یافت نشد
    """
    try:
        session = SessionLocal()
        try:
            ad = session.query(Ads).filter(Ads.id == ad_id).first()
            if not ad:
                return jsonify({"success": False, "error": "تبلیغ یافت نشد"}), 404

            # Delete image file
            if ad.image_url and ad.image_url.startswith('/uploads/'):
                image_path = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), '..',
                    ad.image_url.lstrip('/')
                )
                if os.path.exists(image_path):
                    os.remove(image_path)
                    logger.info(f"Deleted ad image: {image_path}")

            session.delete(ad)
            session.commit()
            logger.info(f"Ad deleted: id={ad_id}")

            return jsonify({
                "success": True,
                "message": "تبلیغ با موفقیت حذف شد"
            })

        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    except Exception as e:
        logger.error(f"Error deleting ad {ad_id}: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "خطا در حذف تبلیغ"
        }), 500


# ═══════════════════════════════════════════════════════════════════
# دریافت یک تبلیغ خاص
# ═══════════════════════════════════════════════════════════════════
@ads_api.route('/ads/<int:ad_id>', methods=['GET'])
def get_ad(ad_id):
    """
    دریافت جزئیات یک تبلیغ
    ---
    tags:
      - Ads
    summary: دریافت جزئیات تبلیغ
    parameters:
      - name: ad_id
        in: path
        required: true
        schema:
          type: integer
    responses:
      '200':
        description: جزئیات تبلیغ
      '404':
        description: تبلیغ یافت نشد
    """
    try:
        session = SessionLocal()
        try:
            ad = session.query(Ads).filter(Ads.id == ad_id).first()
            if not ad:
                return jsonify({"success": False, "error": "تبلیغ یافت نشد"}), 404
            return jsonify({
                "success": True,
                "ad": _ad_to_dict(ad)
            })
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error fetching ad {ad_id}: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "خطا در دریافت تبلیغ"
        }), 500
