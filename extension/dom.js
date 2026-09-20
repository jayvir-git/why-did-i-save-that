(() => {
  'use strict';
  function readableText(node) {
    if (!node) return '';
    if (node.nodeType === 3) return node.textContent;
    if (node.nodeName === 'IMG') return node.getAttribute('alt') || '';
    if (node.nodeName === 'BR') return '\n';
    return Array.from(node.childNodes).map(readableText).join('');
  }
  function readArticle(article, owner, source) {
    if (article.querySelector('[data-testid="placementTracking"]') && !article.querySelector('[data-testid="User-Name"]')) return null;
    const name = article.querySelector('[data-testid="User-Name"]');
    const time = name?.querySelector('time') || article.querySelector('time');
    const match = time?.closest('a')?.getAttribute('href')?.match(/^\/([^/]+)\/status\/(\d+)/);
    if (!match) return null;
    const textNode = Array.from(article.querySelectorAll('[data-testid="tweetText"]')).find(n => !n.closest('[role="link"]'));
    const text = readableText(textNode);
    const nameText = name?.textContent || '';
    const handleAt = nameText.indexOf('@');
    const links = Array.from(article.querySelectorAll('[data-testid="tweetText"] a[href], [data-testid="card.wrapper"] a[href]')).map(a => a.href);
    const media = Array.from(article.querySelectorAll('[data-testid="tweetPhoto"] img')).map(img => ({type:'photo',url:img.src,alt:img.alt || ''}));
    const card = readableText(article.querySelector('[data-testid="card.wrapper"]'));
    const quote = Array.from(article.querySelectorAll('[role="link"]')).find(n => n.querySelector('[data-testid="tweetText"]'));
    const quoteText = readableText(quote?.querySelector('[data-testid="tweetText"]'));
    return {id:match[2], owner, sources:[source], author:match[1], authorName:handleAt > 0 ? nameText.slice(0,handleAt) : match[1],
      text, postedAt:time.getAttribute('datetime'), links, media,
      context: [card, quoteText ? `Quoted post: ${quoteText}` : ''].filter(Boolean).join('\n'), capture:'visible', partial:!!article.querySelector('[data-testid="tweet-text-show-more-link"]') || Array.from(article.querySelectorAll('[role="button"],button')).some(b => b.textContent === 'Show more')
    };
  }
  globalThis.GoldDOM = {readArticle};
})();
