import boto3
import requests
import mimetypes
import uuid
import os
from flask import current_app
from typing import List, Dict, Union, Tuple

class S3Uploader:
    """Enhanced S3 uploader with validation and deletion support"""
    
    # Allowed image file extensions
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'tiff', 'svg'}
    
    # Maximum file size (10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024
    
    @staticmethod
    def allowed_file(filename: str) -> bool:
        """Check if file extension is allowed"""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in S3Uploader.ALLOWED_EXTENSIONS
    
    @staticmethod
    def get_s3_client():
        """Get S3 client with current app config"""
        return boto3.client(
            "s3",
            aws_access_key_id=current_app.config["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=current_app.config["AWS_SECRET_ACCESS_KEY"],
            region_name=current_app.config["AWS_REGION"],
        )
    
    @staticmethod
    def upload_image_to_s3(file_or_url: Union[str, object]) -> str:
        """
        Accepts either:
        - a file upload (jpg/png)
        - a string URL of an image

        Returns a public S3 URL.
        """
        s3 = S3Uploader.get_s3_client()
        bucket = current_app.config["AWS_S3_BUCKET"]

        # Handle image URL
        if isinstance(file_or_url, str):
            response = requests.get(file_or_url)
            if response.status_code != 200:
                raise ValueError(f"Could not download image URL. Status: {response.status_code}")
            file_bytes = response.content
            content_type = response.headers.get("Content-Type", "image/jpeg")
            
            # Validate file size
            if len(file_bytes) > S3Uploader.MAX_FILE_SIZE:
                raise ValueError(f"File too large. Max size: {S3Uploader.MAX_FILE_SIZE // (1024*1024)}MB")

        # Handle file upload
        else:
            file_bytes = file_or_url.read()
            
            # Validate file size
            if len(file_bytes) > S3Uploader.MAX_FILE_SIZE:
                raise ValueError(f"File too large. Max size: {S3Uploader.MAX_FILE_SIZE // (1024*1024)}MB")
            
            # Reset file pointer for potential future use
            file_or_url.seek(0)
            
            content_type = getattr(file_or_url, 'mimetype', None) or "image/jpeg"
            
            # Additional validation for file uploads
            if hasattr(file_or_url, 'filename'):
                if not S3Uploader.allowed_file(file_or_url.filename):
                    raise ValueError(f"File type not allowed. Allowed types: {', '.join(S3Uploader.ALLOWED_EXTENSIONS)}")

        # Build filename
        extension = mimetypes.guess_extension(content_type) or ".jpg"
        filename = f"uploads/{uuid.uuid4()}{extension}"
        
        try:
            # Try with ACL first (for older buckets)
            s3.put_object(
                Bucket=bucket,
                Key=filename,
                Body=file_bytes,
                ContentType=content_type,
                ACL="public-read"
            )
        except Exception as acl_error:
            if "AccessControlListNotSupported" in str(acl_error):
                # ACLs disabled, upload without ACL
                s3.put_object(
                    Bucket=bucket,
                    Key=filename,
                    Body=file_bytes,
                    ContentType=content_type
                )
            else:
                # Some other error
                raise acl_error
        
        return f"https://{bucket}.s3.amazonaws.com/{filename}"
    
    @staticmethod
    def upload_multiple_images(files: List[object]) -> Dict[str, List]:
        """
        Upload multiple images to S3
        
        Args:
            files: List of file objects
            
        Returns:
            Dictionary with 'successful' and 'failed' lists
        """
        results = {
            'successful': [],
            'failed': []
        }
        
        for file in files:
            if file.filename == '':
                continue
                
            try:
                # Validate file type
                if not S3Uploader.allowed_file(file.filename):
                    results['failed'].append({
                        'filename': file.filename,
                        'error': f"File type not allowed. Allowed: {', '.join(S3Uploader.ALLOWED_EXTENSIONS)}"
                    })
                    continue
                
                # Upload to S3
                image_url = S3Uploader.upload_image_to_s3(file)
                
                results['successful'].append({
                    'filename': file.filename,
                    'url': image_url,
                    'key': image_url.split('/')[-2] + '/' + image_url.split('/')[-1]
                })
                
            except Exception as e:
                results['failed'].append({
                    'filename': file.filename,
                    'error': str(e)
                })
        
        return results
    
    @staticmethod
    def delete_image_from_s3(image_url: str) -> bool:
        """
        Delete an image from S3
        
        Args:
            image_url: Full S3 URL or just the key
            
        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            s3 = S3Uploader.get_s3_client()
            bucket = current_app.config["AWS_S3_BUCKET"]
            
            # Extract key from URL
            if image_url.startswith(f"https://{bucket}.s3.amazonaws.com/"):
                key = image_url.replace(f"https://{bucket}.s3.amazonaws.com/", "")
            else:
                key = image_url  # Assume it's already a key
            
            # Delete the object
            s3.delete_object(Bucket=bucket, Key=key)
            
            # Verify deletion (optional)
            try:
                s3.head_object(Bucket=bucket, Key=key)
                # If we get here, object still exists
                return False
            except s3.exceptions.ClientError as e:
                if e.response['Error']['Code'] == '404':
                    # Object not found - successfully deleted
                    return True
                else:
                    # Some other error
                    raise e
                    
        except Exception as e:
            current_app.logger.error(f"Failed to delete image from S3: {str(e)}")
            raise e
    
    @staticmethod
    def delete_multiple_images(image_urls: List[str]) -> Dict[str, List]:
        """
        Delete multiple images from S3
        
        Args:
            image_urls: List of S3 URLs or keys
            
        Returns:
            Dictionary with 'deleted' and 'failed' lists
        """
        results = {
            'deleted': [],
            'failed': []
        }
        
        for image_url in image_urls:
            try:
                success = S3Uploader.delete_image_from_s3(image_url)
                if success:
                    results['deleted'].append(image_url)
                else:
                    results['failed'].append({
                        'url': image_url,
                        'error': 'Failed to verify deletion'
                    })
            except Exception as e:
                results['failed'].append({
                    'url': image_url,
                    'error': str(e)
                })
        
        return results
    
    @staticmethod
    def extract_key_from_url(image_url: str) -> str:
        """
        Extract S3 key from full URL
        
        Args:
            image_url: Full S3 URL
            
        Returns:
            S3 key string
        """
        bucket = current_app.config["AWS_S3_BUCKET"]
        
        if image_url.startswith(f"https://{bucket}.s3.amazonaws.com/"):
            return image_url.replace(f"https://{bucket}.s3.amazonaws.com/", "")
        elif image_url.startswith(f"http://{bucket}.s3.amazonaws.com/"):
            return image_url.replace(f"http://{bucket}.s3.amazonaws.com/", "")
        else:
            # Assume it's already a key
            return image_url
    
    @staticmethod
    def get_image_info(image_url: str) -> Dict:
        """
        Get metadata about an image in S3
        
        Args:
            image_url: Full S3 URL
            
        Returns:
            Dictionary with image metadata
        """
        try:
            s3 = S3Uploader.get_s3_client()
            bucket = current_app.config["AWS_S3_BUCKET"]
            key = S3Uploader.extract_key_from_url(image_url)
            
            response = s3.head_object(Bucket=bucket, Key=key)
            
            return {
                'exists': True,
                'key': key,
                'size': response['ContentLength'],
                'content_type': response['ContentType'],
                'last_modified': response['LastModified'].isoformat() if 'LastModified' in response else None,
                'etag': response.get('ETag', '').strip('"'),
                'metadata': response.get('Metadata', {})
            }
            
        except s3.exceptions.ClientError as e:
            if e.response['Error']['Code'] == '404':
                return {'exists': False, 'key': key, 'error': 'Image not found'}
            else:
                raise e
