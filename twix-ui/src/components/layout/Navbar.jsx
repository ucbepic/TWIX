function Navbar() {
  return (
    <nav className="bg-white shadow-lg">
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex justify-between h-16 items-center">
          <div className="flex items-center">
            <span className="text-2xl font-bold text-blue-600">TWIX</span>
          </div>
          <div className="flex items-center space-x-4">
            <a href="https://github.com/ucbepic/TWIX" className="text-gray-600 hover:text-blue-600">Documentation</a>
          </div>
        </div>
      </div>
    </nav>
  );
}

export default Navbar; 