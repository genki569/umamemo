document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.favorite-btn').forEach(button => {
        button.addEventListener('click', async function(e) {
            e.preventDefault();
            
            try {
                const horseId = this.dataset.horseId;
                const csrfToken = document.querySelector('input[name="csrf_token"]').value;
                
                const response = await fetch(`/toggle_favorite/${horseId}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-CSRFToken': csrfToken,
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: `csrf_token=${csrfToken}`,
                    credentials: 'same-origin'
                });
                
                // 未ログイン時の処理
                if (response.status === 401) {
                    const data = await response.json();
                    if (data.redirect) {
                        window.location.href = data.redirect;
                        return;
                    }
                }
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const data = await response.json();
                if (data.status === 'success') {
                    const icon = this.querySelector('i');
                    if (data.is_favorite) {
                        icon.classList.remove('far');
                        icon.classList.add('fas');
                        this.classList.add('active');
                    } else {
                        icon.classList.remove('fas');
                        icon.classList.add('far');
                        this.classList.remove('active');
                    }
                    
                    if (data.message) {
                        alert(data.message);
                    }
                } else {
                    throw new Error(data.message || 'お気に入りの更新に失敗しました');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('エラーが発生しました');
            }
        });
    });
}); 