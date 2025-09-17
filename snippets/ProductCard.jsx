export const ProductCard = ({ href, icon, title, subtitle, children, links }) => {
  return (
    <div
      className="block p-6 bg-white dark:bg-[#212529] border border-gray-200 dark:border-gray-700 hover:border-[#c1c6cf] rounded-lg dark:hover:border-[#4a4f58] transition-shadow duration-200 cursor-pointer"
      onClick={() => href && (window.location.href = href)}
    >
      <div className="flex items-start">
        {icon && (
          <div className="mr-4 flex-shrink-0" style={{ marginTop: "-12px" }}>
            <img noZoom src={icon} alt="" width="60" height="60" />
          </div>
        )}
        <div className="flex-1 min-w-0">
          <h2 className="text-xl font-bold text-black dark:text-white m-0 mb-1">{title}</h2>
          {subtitle && <h3 className="text-lg font-semibold text-black dark:text-white m-0 mb-3">{subtitle}</h3>}
          <div className="mb-4">{children}</div>
          {links && links.length > 0 && (
            <ul className="list-disc list-inside text-black dark:text-gray-300 space-y-1">
              {links.map((link, index) => (
                <li key={index}>
                  <a
                    href={link.href}
                    className="text-[#038194] dark:text-[#13a9ba]"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {link.text}
                  </a>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
};
