
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import {
  Lock,
  User as UserIcon,
  Eye,
  EyeOff,
  ArrowRight,
  ShieldCheck,
  Factory,
  ClipboardList,
  Crown,
  ShoppingBag,
  Sparkles,
  Building2,
} from "lucide-react";

import { useAuth } from "@/context/AuthContext";
import { getApiErrorMessage } from "@/api/client";

const loginSchema = z.object({
  username: z.string().min(2, "Username is required"),
  password: z.string().min(4, "Password is required"),
});

type LoginForm = z.infer<typeof loginSchema>;

const DEMO_USERS = [
  {
    username: "salesman_a",
    role: "Salesman A",
    description: "Sales & Orders",
    icon: ShoppingBag,
  },
  {
    username: "salesman_b",
    role: "Salesman B",
    description: "Sales & Orders",
    icon: ShoppingBag,
  },
  {
    username: "admin",
    role: "Factory Admin",
    description: "Administration",
    icon: ShieldCheck,
  },
  {
    username: "production",
    role: "Production Supervisor",
    description: "Production Management",
    icon: Factory,
  },
  {
    username: "accountant",
    role: "Accountant",
    description: "Read-only Reports",
    icon: ClipboardList,
  },
  {
    username: "owner",
    role: "Owner",
    description: "Business Overview",
    icon: Crown,
  },
];

export function roleHomePath(role: string): string {
  switch (role) {
    case "salesman":
      return "/salesman";
    case "admin":
      return "/admin/orders";
    case "production":
      return "/production";
    case "accountant":
      return "/reports";
    case "owner":
      return "/owner";
    default:
      return "/owner";
  }
}

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [selectedUser, setSelectedUser] = useState("");

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginForm) => {
    setErrorMsg(null);

    try {
      const user = await login(data.username, data.password);
      navigate(roleHomePath(user.role), { replace: true });
    } catch (err) {
      setErrorMsg(getApiErrorMessage(err, "Invalid credentials"));
    }
  };

  const fillCredentials = (username: string) => {
    setSelectedUser(username);
    setValue("username", username, { shouldValidate: true });
    setValue("password", "demo123", { shouldValidate: true });
  };

  return (
    <div className="min-h-screen relative overflow-hidden bg-[#faf8f3] flex items-center justify-center px-4 py-6">

      {/* Background Decorations */}
      <div className="absolute -top-32 -left-32 w-96 h-96 rounded-full bg-[#e9a45d]/10 blur-3xl pointer-events-none" />
      <div className="absolute -bottom-40 -right-20 w-96 h-96 rounded-full bg-[#b9570b]/10 blur-3xl pointer-events-none" />

      {/* Main Container */}
      <div className="relative w-full max-w-5xl grid lg:grid-cols-[1.05fr_0.95fr] gap-5 items-stretch">

        {/* LEFT LOGIN CARD */}
        <div className="h-full bg-white rounded-3xl border border-[#e9dfd2] shadow-[0_15px_50px_rgba(80,50,20,0.08)] overflow-hidden">

          <div className="h-full p-7 sm:p-8 flex flex-col">

            {/* Brand */}
            <div className="flex items-center gap-4 mb-8">

              <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-[#d97716] to-[#a83e0a] flex items-center justify-center text-white font-black text-lg shadow-lg shadow-orange-900/20">
                O2A
              </div>

              <div>
                <h1 className="text-xl font-bold text-[#30241c] tracking-tight">
                  Order-to-Audit
                </h1>
                <p className="text-xs text-[#88776b]">
                  Kaveri Crunch Foods Pvt. Ltd.
                </p>
              </div>

            </div>

            {/* Heading */}
            <div className="mb-6">

              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#fff3e5] text-[#b9570b] text-xs font-semibold mb-3">
                <Sparkles size={14} />
                Secure Access Portal
              </div>

              <h2 className="text-3xl sm:text-4xl font-bold text-[#30241c] tracking-tight">
                Welcome back!
              </h2>

              <p className="text-[#8a7b70] mt-2 text-sm">
                Sign in to access your workspace and manage operations.
              </p>

            </div>

            {/* Login Form */}
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">

              {errorMsg && (
                <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {errorMsg}
                </div>
              )}

              {/* Username */}
              <div>
                <label className="block text-sm font-semibold text-[#45372d] mb-2">
                  Username
                </label>

                <div className="relative group">

                  <UserIcon
                    size={19}
                    className="absolute left-4 top-1/2 -translate-y-1/2 text-[#a18c7b] group-focus-within:text-[#b9570b] transition-colors"
                  />

                  <input
                    {...register("username")}
                    type="text"
                    placeholder="Enter your username"
                    autoComplete="username"
                    className="w-full h-12 pl-12 pr-4 rounded-xl border border-[#e6d9ca] bg-[#fdfbf8] text-[#30241c] placeholder:text-[#b4a79c] outline-none transition-all focus:border-[#c66a19] focus:ring-4 focus:ring-orange-100"
                  />

                </div>

                {errors.username && (
                  <p className="text-xs text-red-600 mt-1.5">
                    {errors.username.message}
                  </p>
                )}
              </div>

              {/* Password */}
              <div>
                <label className="block text-sm font-semibold text-[#45372d] mb-2">
                  Password
                </label>

                <div className="relative group">

                  <Lock
                    size={19}
                    className="absolute left-4 top-1/2 -translate-y-1/2 text-[#a18c7b] group-focus-within:text-[#b9570b] transition-colors"
                  />

                  <input
                    {...register("password")}
                    type={showPassword ? "text" : "password"}
                    placeholder="Enter your password"
                    autoComplete="current-password"
                    className="w-full h-12 pl-12 pr-12 rounded-xl border border-[#e6d9ca] bg-[#fdfbf8] text-[#30241c] placeholder:text-[#b4a79c] outline-none transition-all focus:border-[#c66a19] focus:ring-4 focus:ring-orange-100"
                  />

                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-[#a18c7b] hover:text-[#b9570b]"
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? <EyeOff size={19} /> : <Eye size={19} />}
                  </button>

                </div>

                {errors.password && (
                  <p className="text-xs text-red-600 mt-1.5">
                    {errors.password.message}
                  </p>
                )}
              </div>

              {/* Sign In */}
              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full h-12 mt-2 rounded-xl bg-gradient-to-r from-[#c7650d] to-[#a94408] hover:from-[#ae5008] hover:to-[#8e3605] text-white font-bold flex items-center justify-center gap-3 shadow-lg shadow-orange-900/15 transition-all duration-300 hover:shadow-xl hover:-translate-y-0.5 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {isSubmitting ? "Signing in..." : "Sign In to Workspace"}
                {!isSubmitting && <ArrowRight size={19} />}
              </button>

            </form>

            {/* Flexible Space */}
            <div className="flex-1 min-h-8" />

            {/* Footer */}
            <div className="mt-5 pt-5 border-t border-[#eee5dc] flex items-center justify-between gap-3">

              <div className="flex items-center gap-2 text-xs text-[#8e8075]">
                <Lock size={14} />
                Secure Login
              </div>

              <div className="text-xs text-[#8e8075]">
                Tiruchirappalli, Tamil Nadu
              </div>

            </div>

          </div>
        </div>

        {/* RIGHT DEMO ACCOUNTS CARD */}
        <div className="h-full relative rounded-3xl border border-[#f0d0a8] bg-gradient-to-br from-[#fffaf1] to-[#fff1df] shadow-[0_15px_50px_rgba(80,50,20,0.06)] overflow-hidden">

          {/* Decorative Circle */}
          <div className="absolute -top-20 -right-20 w-64 h-64 rounded-full border-[35px] border-[#e7a75c]/10 pointer-events-none" />

          <div className="relative p-6 sm:p-7">

            {/* Header */}
            <div className="flex items-start justify-between gap-3 mb-5">

              <div>
                <div className="flex items-center gap-2 mb-1.5">
                  <Building2 size={20} className="text-[#b9570b]" />

                  <h3 className="text-xl font-bold text-[#30241c]">
                    Quick Access
                  </h3>
                </div>

                <p className="text-sm text-[#88776b]">
                  Choose a demo account to get started.
                </p>
              </div>

              <span className="shrink-0 text-[10px] font-bold uppercase tracking-wider text-[#a44c0b] bg-[#ffebcd] border border-[#f1d0a2] px-3 py-2 rounded-full">
                Demo Mode
              </span>

            </div>

            {/* Demo Password */}
            <div className="mb-4 p-3 rounded-xl bg-white/80 border border-[#f0dfca]">

              <p className="text-xs text-[#88776b] mb-1">
                Common demo password
              </p>

              <div className="flex items-center justify-between">

                <code className="text-sm font-bold tracking-wider text-[#a94c0a]">
                  demo123
                </code>

                <span className="text-xs text-[#8c806f]">
                  All accounts
                </span>

              </div>
            </div>

            {/* Demo Accounts */}
            <div className="space-y-2">

              {DEMO_USERS.map((u) => {
                const Icon = u.icon;
                const isSelected = selectedUser === u.username;

                return (
                  <button
                    key={u.username}
                    type="button"
                    onClick={() => fillCredentials(u.username)}
                    className={`w-full group flex items-center gap-3 py-2.5 px-4 rounded-xl border text-left transition-all duration-200 ${isSelected
                        ? "border-[#c66a19] bg-[#fff1df] shadow-md shadow-orange-900/5"
                        : "border-[#eadcc9] bg-white/90 hover:border-[#d58a42] hover:bg-white hover:shadow-md"
                      }`}
                  >

                    {/* Icon */}
                    <div className={`w-9 h-9 shrink-0 rounded-lg flex items-center justify-center transition-colors ${isSelected
                        ? "bg-[#b9570b] text-white"
                        : "bg-[#fff0df] text-[#b9570b] group-hover:bg-[#f8dfc2]"
                      }`}>
                      <Icon size={19} />
                    </div>

                    {/* Account Details */}
                    <div className="flex-1 min-w-0">

                      <p className="font-semibold text-sm text-[#30241c]">
                        {u.role}
                      </p>

                      <p className="text-xs text-[#978477] mt-0.5">
                        {u.description}
                      </p>

                      <p className="text-[10px] text-[#ad6b36] font-mono mt-0.5">
                        {u.username}
                      </p>

                    </div>

                    {/* Fill Button */}
                    <div className={`shrink-0 px-3 py-1 rounded-lg text-xs font-semibold transition-colors ${isSelected
                        ? "bg-[#b9570b] text-white"
                        : "bg-[#fff6eb] text-[#a65a1a] border border-[#eedcc8] group-hover:bg-[#b9570b] group-hover:text-white"
                      }`}>
                      {isSelected ? "Selected" : "Fill"}
                    </div>

                  </button>
                );
              })}

            </div>

            {/* Information Note */}
            <div className="mt-5 flex items-start gap-3 p-3 rounded-xl bg-[#f9ead6]/70 border border-[#efd8b8]">

              <ShieldCheck size={18} className="text-[#a95713] shrink-0 mt-0.5" />

              <p className="text-[11px] text-[#846d59] leading-relaxed">
                These accounts are provided for development and demonstration
                purposes only. Select a role to automatically fill the login
                credentials.
              </p>

            </div>

          </div>
        </div>

      </div>
    </div>
  );
}
