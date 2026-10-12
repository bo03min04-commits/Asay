// 외부 프레임워크 없이 동작하는 작은 상호작용만 사용합니다.
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('form').forEach(form => {
    form.addEventListener('submit', () => {
      const button = form.querySelector('button[type="submit"]');
      if (button && form.checkValidity()) {
        button.disabled = true;
        button.classList.add('is-loading');
        const label = button.textContent.trim();
        button.textContent = '처리 중…';
        // 브라우저의 form submit이 실패하여 돌아왔을 때 조작할 수 있도록 시간 경과시 복구하지 않음.
      }
    });
  });
});
