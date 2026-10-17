-- Point relative links to other Markdown pages at their rendered .html.
function Link(el)
  if not el.target:match('^%a[%w+.-]*:') then
    el.target = el.target:gsub('%.md$', '.html'):gsub('%.md#', '.html#')
  end
  return el
end
