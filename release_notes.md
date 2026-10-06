# CutVideo v1.0.0 🚀

Đây là phiên bản chính thức đầu tiên của ứng dụng **CutVideo** - công cụ cắt video nhanh gọn và chuyên nghiệp!

## ✨ Tính năng nổi bật
*   **Giao diện trực quan:** Tích hợp trình phát video ngay trong ứng dụng, cho phép bạn xem trước video và kéo thả thanh trượt để chọn đoạn cắt dễ dàng. Hỗ trợ "Click-to-seek" (Click thẳng vào thanh trượt để tua nhanh).
*   **Điều khiển âm thanh:** Hỗ trợ tính năng Bật/Tắt (Mute) và điều chỉnh âm lượng (Volume) trực tiếp trong lúc xem video.
*   **Cắt video "siêu tốc" không giảm chất lượng:** Chế độ "Gốc" cắt video siêu nhanh bằng cách không giải mã lại luồng dữ liệu (lossless).
*   **Tăng tốc bằng phần cứng (NVIDIA GPU):** Hỗ trợ xuất file (render) với tốc độ tên lửa dành cho các máy tính sử dụng card đồ họa NVIDIA (công nghệ NVENC).
*   **Nối (Append) 2 video liền mạch:** Tab mới cho phép chọn và ghép 2 video lại với nhau theo thứ tự mong muốn:
    *   Hỗ trợ nút đảo thứ tự (Swap Video 1 ⇄ Video 2) nhanh chóng.
    *   **Chế độ Tương thích cao (Khuyên dùng):** Tự động chuẩn hóa kích thước, tỉ lệ khung hình (letterbox/pad không méo hình) và tần số âm thanh, giúp ghép thành công mọi video dù khác độ phân giải hoặc fps.
    *   **Chế độ Siêu tốc (Stream Copy):** Ghép tức thì không encode lại nếu 2 video cùng định dạng và kích thước.
    *   Tích hợp trình phát xem thử từng video trước khi ghép.
*   **Thanh tiến trình (Progress Bar):** Theo dõi % xuất video theo thời gian thực trực quan, hỗ trợ hủy (Cancel) giữa chừng và tự động dọn rác.
*   **Gói độc lập (Standalone):** Đã đóng gói thành file `.exe` chạy không cần cài đặt Python hay cấu hình rườm rà.

## 🛠 Cách cài đặt và sử dụng
1. Tải xuống file nén **`CutVideo-v1.zip`** ở mục *Assets* bên dưới.
2. Giải nén thư mục ra màn hình máy tính hoặc bất kỳ đâu.
3. Chạy trực tiếp file `CutVideo.exe` bên trong thư mục vừa giải nén để bắt đầu cắt video ngay!
