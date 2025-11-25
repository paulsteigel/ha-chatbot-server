# HA Entity Endpoint Add-on

Author: Đặng Đình Ngọc (ngocdd@sfdp.net)

## Giới thiệu

Add-on này cung cấp API endpoints cho phép thiết bị từ xa (như ESP32S3) truy vấn và điều khiển các thiết bị Home Assistant.

## Cấu hình

1. **access_token**: Token xác thực cho ESP32S3 (bắt buộc)
2. **ha_url**: URL của Home Assistant (mặc định: http://supervisor/core)

## API Endpoints

Tất cả endpoints yêu cầu header: `Authorization: Bearer YOUR_TOKEN`

### 1. Lấy danh sách vùng
