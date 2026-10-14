import Link from "next/link";

import { formatMoney, type RecentOrderItem } from "@/lib/ops-api";
import { orderStatusLabel } from "@/lib/orders-api";

type Props = {
  orders: RecentOrderItem[];
};

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString("es-EC", {
      dateStyle: "short",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

export function RecentOrders({ orders }: Props) {
  return (
    <section className="gema-panel flex h-full flex-col overflow-hidden">
      <div className="flex items-baseline justify-between gap-2 border-b border-border px-5 py-4">
        <div>
          <h2 className="font-display text-lg font-semibold">Actividad reciente</h2>
          <p className="mt-1 text-sm text-secondary">Últimos pedidos registrados</p>
        </div>
        <Link href="/admin/orders" className="text-sm text-cyan underline">
          Ver todos
        </Link>
      </div>
      <div className="overflow-x-auto">
        <table className="gema-table">
          <thead>
            <tr>
              <th>Pedido</th>
              <th>Cliente</th>
              <th>Estado</th>
              <th>Total</th>
              <th>Fecha</th>
            </tr>
          </thead>
          <tbody>
            {orders.length === 0 ? (
              <tr>
                <td colSpan={5} className="text-secondary">
                  Aún no hay pedidos.
                </td>
              </tr>
            ) : (
              orders.map((order) => (
                <tr key={order.id}>
                  <td>
                    <Link
                      href={`/admin/orders/${order.id}`}
                      className="text-cyan underline"
                    >
                      {order.order_number}
                    </Link>
                  </td>
                  <td className="max-w-[12rem] truncate">
                    {order.customer_email ?? "—"}
                  </td>
                  <td>{orderStatusLabel(order.status)}</td>
                  <td className="tabular-nums">
                    {formatMoney(order.total, order.currency)}
                  </td>
                  <td className="whitespace-nowrap text-secondary">
                    {formatDate(order.created_at)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
