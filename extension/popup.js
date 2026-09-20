document.querySelector('#library').onclick = () => chrome.tabs.create({url:chrome.runtime.getURL('library.html')});
