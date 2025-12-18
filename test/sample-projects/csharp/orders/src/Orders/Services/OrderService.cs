using Orders.Models;
using Orders.Repositories;

namespace Orders.Services;

public class OrderService
{
    private readonly IOrderRepository _repo;

    public OrderService(IOrderRepository repo)
    {
        _repo = repo;
    }

    public Order Create(string id, int quantity)
    {
        var order = new Order(id, quantity, false);
        _repo.Save(order);
        return order;
    }

    public Order? MarkPaid(string id)
    {
        var order = _repo.Find(id);
        if (order == null) return null;
        var updated = order with { Paid = true };
        _repo.Update(updated);
        return updated;
    }
}