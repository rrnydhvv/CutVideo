# CutVideo v1.3.0 🚀

Phiên bản **CutVideo v1.3.0** bổ sung tính năng Nối (Append) 2 video liền mạch và tối ưu hóa khả năng tương thích toàn diện trên mọi thiết bị và nền tảng!

## ✨ Tính năng nổi bật
*   **Giao diện trực quan:** Tích hợp trình phát video ngay trong ứng dụng, cho phép bạn xem trước video và kéo thả thanh trượt để chọn đoạn cắt dễ dàng. Hỗ trợ "Click-to-seek" (Click thẳng vào thanh trượt để tua nhanh).
*   **Điều khiển âm thanh:** Hỗ trợ tính năng Bật/Tắt (Mute) và điều chỉnh âm lượng (Volume) trực tiếp trong lúc xem video.
*   **Cắt video "siêu tốc" không giảm chất lượng:** Chế độ "Gốc" cắt video siêu nhanh bằng cách không giải mã lại luồng dữ liệu (lossless).
*   **Tăng tốc bằng phần cứng (NVIDIA GPU):** Hỗ trợ xuất file (render) với tốc độ tên lửa dành cho các máy tính sử dụng card đồ họa NVIDIA (công nghệ NVENC).
*   **Nối (Append) 2 video liền mạch & Tương thích tối đa:** Tab mới cho phép chọn và ghép 2 video lại với nhau theo thứ tự mong muốn:
    *   Hỗ trợ nút đảo thứ tự (Swap Video 1 ⇄ Video 2) nhanh chóng.
    *   **Bảng phân tích tương thích tự động:** Tự động phát hiện và cảnh báo độ lệch về độ phân giải, FPS, codec video/audio hoặc video không có tiếng trước khi ghép.
    *   **Chế độ Tương thích cao (Khuyên dùng):**
        *   Tự động chuẩn hóa kích thước và tỉ lệ khung hình (letterbox/pad căn giữa không méo hình, đảm bảo tọa độ chẵn cho YUV420p).
        *   Khử hoàn toàn lệch tiếng/giật hình với `setpts=PTS-STARTPTS` và `aresample=async=1:first_pts=0`.
        *   Tự động bù âm thanh tĩnh (silent audio) khớp thời lượng nếu một trong hai video không có âm thanh.
        *   Tùy chọn linh hoạt khung hình đích (Theo Video 1, Lớn nhất, 1080p, 720p, Shorts/TikTok 9:16) và FPS (Tự động, 30, 60).
        *   Chuẩn hóa định dạng màu sắc `yuv420p`, tốc độ khung hình cố định `CFR` và cờ `-movflags +faststart` giúp tương thích 100% trên mọi nền tảng (web, mobile, TV, mạng xã hội).
    *   **Chế độ Siêu tốc (Stream Copy):** Ghép tức thì không encode lại nếu 2 video cùng định dạng; tự động khắc phục lỗi mốc thời gian âm (`-avoid_negative_ts make_zero`).
    *   **Tự động chuyển đổi & thử lại thông minh (Smart Fallback):** Cảnh báo trước khi ghép siêu tốc và tự động gợi ý thử lại bằng chế độ 'Tương thích cao' nếu ghép siêu tốc thất bại.
    *   Tích hợp trình phát xem thử từng video trước khi ghép.
*   **Thanh tiến trình (Progress Bar):** Theo dõi % xuất video theo thời gian thực trực quan, hỗ trợ hủy (Cancel) giữa chừng và tự động dọn rác.
*   **Gói độc lập (Standalone):** Đã đóng gói thành file `.exe` chạy không cần cài đặt Python hay cấu hình rườm rà.

## 🛠 Cách cài đặt và sử dụng
1. Tải xuống file nén **`CutVideo-v1.zip`** ở mục *Assets* bên dưới.
2. Giải nén thư mục ra màn hình máy tính hoặc bất kỳ đâu.
3. Chạy trực tiếp file `CutVideo.exe` bên trong thư mục vừa giải nén để bắt đầu cắt video ngay!
