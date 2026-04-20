import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, X, Download } from "lucide-react";
import { Button } from "@/components/ui/button";

const navLinks = [
  { label: "Home", to: "/" },
  { label: "Features", to: "/features" },
  { label: "Workflow", to: "/workflow" },
  { label: "Security Review", to: "/security-review" },
  { label: "Download", to: "/download" },
  { label: "FAQ & Contact", to: "/faq-contact" },
];

export function Navbar() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-background border-b border-border-soft">
      <div className="max-w-content mx-auto px-6 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2.5">
          <img src="/icon.png" alt="Aegix" className="w-8 h-8 rounded-lg" />
          <span className="font-semibold text-foreground tracking-tight font-serif">Aegix</span>
        </Link>

        <div className="hidden lg:flex items-center gap-1">
          {navLinks.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
                location.pathname === link.to
                  ? "text-foreground font-medium bg-muted"
                  : "text-text-secondary hover:text-foreground hover:bg-muted/50"
              }`}
            >
              {link.label}
            </Link>
          ))}
        </div>

        <div className="hidden lg:flex items-center gap-3">
          <Link to="/signin">
            <span className="text-sm text-text-secondary hover:text-foreground transition-colors cursor-pointer px-3 py-1.5">
              Sign in
            </span>
          </Link>
          <Link to="/download">
            <Button size="sm" className="gap-2 bg-foreground text-background hover:bg-foreground/90 rounded-md">
              <Download className="w-3.5 h-3.5" />
              Download
            </Button>
          </Link>
        </div>

        <button
          className="lg:hidden p-2 rounded-md hover:bg-muted"
          onClick={() => setMobileOpen(!mobileOpen)}
        >
          {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="lg:hidden border-t border-border-soft bg-background overflow-hidden"
          >
            <div className="px-6 py-4 flex flex-col gap-1">
              {navLinks.map((link) => (
                <Link
                  key={link.to}
                  to={link.to}
                  onClick={() => setMobileOpen(false)}
                  className={`px-3 py-2.5 rounded-md text-sm transition-colors ${
                    location.pathname === link.to
                      ? "text-foreground font-medium bg-muted"
                      : "text-text-secondary hover:text-foreground"
                  }`}
                >
                  {link.label}
                </Link>
              ))}
              <div className="pt-3 border-t border-border-soft mt-2 flex flex-col gap-2">
                <Link to="/signin" onClick={() => setMobileOpen(false)} className="px-3 py-2.5 rounded-md text-sm text-text-secondary hover:text-foreground text-center">
                  Sign in
                </Link>
                <Link to="/download" onClick={() => setMobileOpen(false)}>
                  <Button className="w-full gap-2 bg-foreground text-background hover:bg-foreground/90">
                    <Download className="w-3.5 h-3.5" />
                    Download
                  </Button>
                </Link>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </nav>
  );
}
