// Show a preview enlarged in a modal dialog. Without JavaScript, the link opens the GIF.
const lightbox = document.createElement('dialog');
const closeButton = document.createElement('button');
const lightboxImage = document.createElement('img');
lightbox.className = 'lightbox';
closeButton.type = 'button';
closeButton.setAttribute('aria-label', 'Close preview');
lightboxImage.alt = '';
closeButton.append(lightboxImage);
lightbox.append(closeButton);
document.body.append(lightbox);

// A click on the image, its frame, or the backdrop closes the dialog, as does Escape.
lightbox.addEventListener('click', () => lightbox.close());

for (const link of document.querySelectorAll('.preview')) {
  link.addEventListener('click', (event) => {
    // Leave modified clicks to the browser, such as opening the GIF in a new tab.
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    const preview = link.querySelector('img');
    // The size comes from the markup, so the image need not have loaded yet.
    lightboxImage.style.setProperty(
      '--ratio',
      `${preview.getAttribute('width')} / ${preview.getAttribute('height')}`,
    );
    lightboxImage.src = link.href;
    lightbox.setAttribute('aria-label', preview.alt);
    lightbox.showModal();
  });
}
