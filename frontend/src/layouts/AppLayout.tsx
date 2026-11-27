import React from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  BarChart3,
  Boxes,
  ClipboardCheck,
  CreditCard,
  Factory,
  FileSpreadsheet,
  FileText,
  History,
  LogOut,
  Moon,
  Package,
  ShoppingCart,
  Sun,
  Truck,
  Users,
} from "lucide-react";
import { useAuth, type UserRole } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface NavItem {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  roles: UserRole[];
}

const NAV_ITEMS: NavItem[] = [
  { to: "/salesman", label: "Mobile Order", icon: ShoppingCart, roles: ["salesman"] },
  { to: "/salesman/history", label: "My Orders", icon: History, roles: ["salesman"] },
  { to: "/owner", label: "Owner Dashboard", icon: BarChart3, roles: ["owner", "admin"] },
  { to: "/admin/orders", label: "Orders & Approval", icon: ClipboardCheck, roles: ["admin"] },
  { to: "/admin/invoices", label: "GST Invoices & Dispatch", icon: FileText, roles: ["admin", "accountant", "owner"] },
  { to: "/admin/payments", label: "Payments & Dues", icon: CreditCard, roles: ["admin", "accountant", "owner"] },
  { to: "/admin/masters", label: "Masters & Prices", icon: Users, roles: ["admin"] },
  { to: "/production", label: "Production & BOM", icon: Factory, roles: ["production", "admin"] },
  { to: "/production/purchases", label: "Purchases & Suppliers", icon: Truck, roles: ["production", "admin"] },
  { to: "/inventory", label: "Inventory & Ledger", icon: Boxes, roles: ["production", "admin", "accountant", "owner"] },
  { to: "/costing", label: "Costing & Margins", icon: Package, roles: ["production", "admin", "accountant", "owner"] },
  { to: "/reports", label: "Monthly Reports", icon: FileSpreadsheet, roles: ["accountant", "admin", "owner"] },
  { to: "/audit", label: "Audit Trail", icon: History, roles: ["accountant", "admin", "owner"] },
];

export function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const { dark, toggleDark } = useTheme();
  const navigate = useNavigate();

  if (!user) return null;

  const visibleItems = NAV_ITEMS.filter((item) => item.roles.includes(user.role));

  return (
    <div className="min-h-screen flex flex-col md:flex-row bg-background">
      {/* Desktop Sidebar */}
      <aside className="hidden md:flex md:w-64 md:flex-col border-r border-border bg-card">
        <div className="p-5 border-b border-border flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-turmeric-500 to-terracotta-600 flex items-center justify-center text-white font-bold shadow-sm">
            O2A
          </div>
          <div>
            <div className="font-bold text-sm leading-tight">Order-to-Audit</div>
            <div className="text-xs text-muted-foreground">Kaveri Crunch Foods</div>
          </div>
        </div>
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {visibleItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/salesman" || item.to === "/production"}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-primary text-primary-foreground shadow-sm"
                      : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                  }`
                }
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>
        <div className="p-4 border-t border-border space-y-3">
          <div className="flex items-center justify-between">
            <div className="min-w-0">
              <div className="text-sm font-medium truncate">{user.full_name}</div>
              <Badge variant="default" className="mt-1 capitalize">
                {user.role}
              </Badge>
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" className="flex-1" onClick={toggleDark}>
              {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              <span>{dark ? "Light" : "Dark"}</span>
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                logout();
                navigate("/login");
              }}
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 pb-16 md:pb-0">
        {/* Top Bar */}
        <header className="sticky top-0 z-30 h-14 border-b border-border bg-card/95 backdrop-blur px-4 flex items-center justify-between">
          <div className="flex items-center gap-2 md:hidden">
            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-turmeric-500 to-terracotta-600 flex items-center justify-center text-white text-xs font-bold">
              O2A
            </div>
            <span className="font-semibold text-sm">Order-to-Audit</span>
          </div>
          <div className="hidden md:flex items-center gap-2 text-xs text-muted-foreground">
            <span>Tiruchirappalli, Tamil Nadu (GSTIN: 33AABCK4821M1Z7)</span>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="secondary" className="capitalize hidden sm:inline-flex">
              {user.role}
            </Badge>
            <Button variant="ghost" size="icon" onClick={toggleDark} className="md:hidden" aria-label="Toggle theme">
              {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="md:hidden"
              onClick={() => {
                logout();
                navigate("/login");
              }}
              aria-label="Logout"
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </header>

        <main className="flex-1 p-4 md:p-6 max-w-7xl w-full mx-auto">{children}</main>
      </div>

      {/* Mobile Bottom Navigation */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 border-t border-border bg-card/95 backdrop-blur flex justify-around py-1.5 px-1">
        {visibleItems.slice(0, 5).map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/salesman" || item.to === "/production"}
              className={({ isActive }) =>
                `flex flex-col items-center gap-0.5 px-2 py-1 rounded-lg text-[11px] font-medium ${
                  isActive ? "text-primary" : "text-muted-foreground"
                }`
              }
            >
              <Icon className="h-5 w-5" />
              <span className="truncate max-w-[68px]">{item.label.split(" ")[0]}</span>
            </NavLink>
          );
        })}
      </nav>
    </div>
  );
}
