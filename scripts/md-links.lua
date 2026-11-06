-- Point local Markdown page links at their rendered .html, preserving downloads.
function Link(el)
  if not el.target:match('^%a[%w+.-]*:') and not el.target:match('^//') then
    local path, suffix = el.target:match('^([^?#]*)(.*)$')
    if not ('/' .. path):match('/download/') then
      el.target = path:gsub('%.md$', '.html') .. suffix
    end
  end
  return el
end

-- Pandoc template conditionals test booleans, so derive this flag from lang.
function Meta(meta)
  meta['lang-cs'] = meta.lang ~= nil and pandoc.utils.stringify(meta.lang) == 'cs'
  return meta
end
