function Footer() {
  return (
    <footer className="bg-gray-800 text-white mt-auto">
      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="text-center">
          <p className="text-sm">© {new Date().getFullYear()}</p>
        </div>
      </div>
    </footer>
  );
}

export default Footer; 