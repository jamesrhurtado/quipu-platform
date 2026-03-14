"use client";

import { useRouter } from "next/navigation";
import OnboardingWizard from "@/components/OnboardingWizard";

export default function SetupPage() {
  const router = useRouter();

  return (
    <OnboardingWizard
      onComplete={() => {
        router.replace("/dashboard");
      }}
    />
  );
}
