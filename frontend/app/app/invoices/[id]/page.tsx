"use client";

import { use, useState } from "react";
import { InvoicePreview } from "@/components/invoice-preview";
import { InvoiceReviewForm } from "@/components/invoice-review-form";
import { api, type InvoiceDetail } from "@/lib/api";
import { useEffect } from "react";

export default function ReviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [inv, setInv] = useState<InvoiceDetail | null>(null);

  useEffect(() => {
    api.get<InvoiceDetail>(`/api/invoices/${id}`).then(setInv).catch(() => {});
  }, [id]);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="h-[70vh]">
          <InvoicePreview url={inv?.file_preview_url ?? null} filename={inv?.original_filename ?? ""} />
        </div>
        <div className="rounded-lg border bg-white p-4">
          <h2 className="mb-3 text-base font-semibold">{inv?.original_filename ?? id}</h2>
          <InvoiceReviewForm id={id} />
        </div>
      </div>
    </div>
  );
}