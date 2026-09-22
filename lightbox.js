const lightbox = document.getElementById('lightbox');
const lightboxImage = document.getElementById('lightbox-img');
const LIGHTBOX_PADDING = 32;

function closeLightbox() {
  lightbox.style.display = 'none';
  document.body.classList.remove('lightbox-open');
}

lightbox.addEventListener('click', closeLightbox);
lightbox.addEventListener(
  'touchmove',
  event => event.preventDefault(),
  { passive: false }
);

document.querySelectorAll('.card img').forEach(image => {
  image.style.cursor = 'pointer';
  image.addEventListener('click', event => {
    event.preventDefault();
    // Scale image to fit the viewport while keeping pixel art sharp.
    const previewImage = new Image();
    previewImage.onload = () => {
      const maxWidth = window.innerWidth * 0.85 - LIGHTBOX_PADDING * 2;
      const maxHeight = window.innerHeight * 0.85 - LIGHTBOX_PADDING * 2;
      const scale = Math.min(
        maxWidth / previewImage.naturalWidth,
        maxHeight / previewImage.naturalHeight
      );
      lightboxImage.style.width = (previewImage.naturalWidth * scale) + 'px';
      lightboxImage.style.height = (previewImage.naturalHeight * scale) + 'px';
      lightboxImage.src = image.src;
      document.body.classList.add('lightbox-open');
      lightbox.style.display = 'flex';
    };
    previewImage.src = image.src;
  });
});
